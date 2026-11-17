import json
import logging
import os
import sys
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from broker import QUEUE, connect, publish


def rest(function, **params):
    data = urlencode(dict(params, wsfunction=function,
                          wstoken=os.environ["MOODLE_TOKEN"],
                          moodlewsrestformat="json")).encode()
    request = Request(os.environ["MOODLE_API"], data=data, headers={"Host": os.environ.get("MOODLE_PUBLIC_HOST", "localhost:8080")})
    with urlopen(request, timeout=15) as response:
        result = json.load(response)
    if isinstance(result, dict) and ("exception" in result or result.get("warnings")):
        detalhe = result.get("errorcode") or result.get("exception") or "warnings" if isinstance(result, dict) else ""
        raise RuntimeError(f"Resposta Moodle incompleta em {function}: {detalhe}")
    return result


def reminders(api, course, base, now):
    courses = api("mod_assign_get_assignments", **{"courseids[0]": course})["courses"]
    course_data = next((c for c in courses if c["id"] == course), None)
    if course_data is None:
        raise RuntimeError(f"Curso {course} não retornado pelo Moodle (confira MOODLE_COURSE_ID e a matrícula da conta de integração)")
    tasks = [a for a in course_data["assignments"]
             if now < a["duedate"] <= now + 86400
             and a.get("allowsubmissionsfromdate", 0) <= now
             and not a.get("teamsubmission", 0)]
    if not tasks:
        return
    users = api("core_enrol_get_enrolled_users", courseid=course,
                **{"options[0][name]": "onlyactive", "options[0][value]": 1})
    students = [u for u in users if any(r["shortname"] == "student" for r in u.get("roles", []))]
    for a in tasks:
        aid = a["id"]
        result = api("mod_assign_get_submissions", **{"assignmentids[0]": aid})
        record = next(row for row in result["assignments"] if row["assignmentid"] == aid)
        latest = {}
        for s in record["submissions"]:
            uid = s["userid"]
            if uid not in latest or s.get("attemptnumber", 0) > latest[uid].get("attemptnumber", 0):
                latest[uid] = s
        for u in students:
            uid = u["id"]
            if latest.get(uid, {}).get("status") == "submitted":
                continue
            if not u.get("email"):
                logging.warning("Aluno %s sem e-mail disponível pela API", uid)
                continue
            yield dict(id=f"{course}:{aid}:{uid}", email=u["email"], task=a["name"],
                       due=a["duedate"], url=f"{base.rstrip('/')}/mod/assign/view.php?id={a['cmid']}")


def main():
    logging.basicConfig(level=logging.INFO)
    if not os.getenv("MOODLE_TOKEN") or not os.getenv("MOODLE_COURSE_ID"):
        sys.exit("Preencha MOODLE_TOKEN e MOODLE_COURSE_ID no .env.")
    course = int(os.environ["MOODLE_COURSE_ID"])
    interval = max(1, int(os.getenv("POLL_SECONDS", "3600")))
    while True:
        try:
            messages = list(reminders(rest, course, os.environ["MOODLE_PUBLIC_URL"], int(time.time())))
            conn, channel = connect()
            try:
                for msg in messages:
                    publish(channel, QUEUE, json.dumps(msg).encode())
            finally:
                conn.close()
            logging.info("Consulta concluída: %d solicitações", len(messages))
        except Exception as exc:
            logging.error("Falha na consulta/publicação: %s: %s", type(exc).__name__, exc)
        time.sleep(interval)


if __name__ == "__main__":
    main()
