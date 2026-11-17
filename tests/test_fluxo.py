import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from acompanhamento import reminders
from notificacoes import handle, open_db, process


class Fluxo(unittest.TestCase):
    def test_selecao(self):
        now = 1800000000
        tasks = [dict(id=i, cmid=100+i, duedate=d, name=str(i))
                 for i, d in enumerate([0, now-1, now, now+1, now+86400, now+86401])]
        tasks += [dict(id=8, duedate=now+10, teamsubmission=1)]
        def api(fn, **params):
            if fn == "mod_assign_get_assignments":
                return {"courses": [{"id": 2, "assignments": tasks}]}
            if fn == "core_enrol_get_enrolled_users":
                return [dict(id=i, email=f"u{i}@example.test", roles=[{"shortname": role}])
                        for i, role in [(1, "student"), (2, "student"), (3, "teacher")]]
            aid = params["assignmentids[0]"]
            return {"assignments": [{"assignmentid": aid, "submissions":
                    [{"userid": 2, "status": "submitted"}]}]}
        result = list(reminders(api, 2, "http://localhost:8080", now))
        self.assertEqual([r["id"] for r in result], ["2:3:1", "2:4:1"])
        self.assertTrue(result[0]["url"].endswith("id=103"))

    def test_falha_nova_tentativa_e_deduplicacao_persistente(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "state.sqlite"
            db = open_db(path)
            msg = dict(id="2:3:1", email="a@example.test", due=1800000000,
                       task="Teste", url="http://localhost:8080")
            body = json.dumps(msg).encode()
            smtp = Mock(side_effect=[ConnectionError(), None])
            channel = Mock()
            delivery = SimpleNamespace(delivery_tag=12)
            with patch("notificacoes.publish") as publish, patch("notificacoes.time.time", return_value=1700000000):
                handle(db, channel, delivery, SimpleNamespace(headers={}), body, smtp)
                publish.assert_called_once_with(channel, "lembretes.retry", body, 2)
                channel.basic_ack.assert_called_once_with(12)
                handle(db, channel, delivery, SimpleNamespace(headers={"attempt": 2}), body, smtp)
            db.close()
            db = open_db(path)
            self.assertEqual(process(db, msg, smtp, 1700000001), "duplicado")
            self.assertEqual(process(db, dict(msg, id="novo"), smtp, msg["due"]), "vencido")
            self.assertEqual(smtp.call_count, 2)
            db.close()


def _api(subs, assignment=None, users=None):
    now = 1800000000
    a = dict(id=1, cmid=9, duedate=now + 3600, name="T")
    a.update(assignment or {})
    users = users if users is not None else [
        dict(id=1, email="a@example.test", roles=[{"shortname": "student"}]),
        dict(id=2, email="", roles=[{"shortname": "student"}]),
    ]

    def api(fn, **params):
        if fn == "mod_assign_get_assignments":
            return {"courses": [{"id": 2, "assignments": [a]}]}
        if fn == "core_enrol_get_enrolled_users":
            return users
        return {"assignments": [{"assignmentid": 1, "submissions": subs}]}
    return api, now


class Bordas(unittest.TestCase):
    def ids(self, subs, **kw):
        api, now = _api(subs, **kw)
        return [r["id"] for r in reminders(api, 2, "http://h", now)]

    def test_rascunho_e_pendencia(self):
        self.assertEqual(self.ids([dict(userid=1, status="draft", attemptnumber=0)]), ["2:1:1"])

    def test_entrega_enviada_nao_gera_lembrete(self):
        self.assertEqual(self.ids([dict(userid=1, status="submitted", attemptnumber=0)]), [])

    def test_tentativa_mais_recente_vale(self):
        subs = [dict(userid=1, status="submitted", attemptnumber=0),
                dict(userid=1, status="new", attemptnumber=1)]
        self.assertEqual(self.ids(subs), ["2:1:1"])

    def test_tarefa_ainda_nao_aberta_ou_sem_prazo(self):
        self.assertEqual(self.ids([], assignment=dict(allowsubmissionsfromdate=1800000010)), [])
        self.assertEqual(self.ids([], assignment=dict(duedate=0)), [])

    def test_aluno_sem_email_e_ignorado(self):
        self.assertNotIn("2:1:2", self.ids([]))

    def test_curso_ausente_gera_erro_claro(self):
        def api(fn, **p):
            return {"courses": []}
        with self.assertRaises(RuntimeError):
            list(reminders(api, 2, "http://h", 1800000000))


class Notificacao(unittest.TestCase):
    def test_mensagem_invalida_vai_para_falhas(self):
        with tempfile.TemporaryDirectory() as folder:
            db = open_db(Path(folder) / "s.sqlite")
            channel, sender = Mock(), Mock()
            with patch("notificacoes.publish") as publish:
                handle(db, channel, SimpleNamespace(delivery_tag=1), SimpleNamespace(headers=None), b"{ruim", sender)
                publish.assert_called_once_with(channel, "lembretes.falhas", b"{ruim", 1)
            sender.assert_not_called()
            channel.basic_ack.assert_called_once_with(1)
            db.close()

    def test_terceira_falha_vai_para_fila_de_falhas(self):
        with tempfile.TemporaryDirectory() as folder:
            db = open_db(Path(folder) / "s.sqlite")
            msg = dict(id="2:3:1", email="a@example.test", due=4102444800, task="T", url="http://h")
            body = json.dumps(msg).encode()
            channel = Mock()
            with patch("notificacoes.publish") as publish:
                handle(db, channel, SimpleNamespace(delivery_tag=1), SimpleNamespace(headers={"attempt": 3}),
                       body, Mock(side_effect=ConnectionError()))
                publish.assert_called_once_with(channel, "lembretes.falhas", body, 3)
            db.close()

    def test_email_tem_tarefa_prazo_e_link(self):
        import notificacoes
        enviados = []
        class FakeSMTP:
            def __init__(self, *a, **k): pass
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def send_message(self, m): enviados.append(m)
        msg = dict(id="x", email="a@example.test", task="Entrega 1", due=1800000000,
                   url="http://localhost:8080/mod/assign/view.php?id=5")
        with patch.dict("os.environ", {"SMTP_HOST": "h", "SMTP_PORT": "1025"}), \
             patch.object(notificacoes.smtplib, "SMTP", FakeSMTP):
            notificacoes.send(msg)
        corpo = enviados[0].get_content()
        self.assertIn("Entrega 1", corpo)
        self.assertIn("15/01/2027 às 05:00", corpo)
        self.assertIn("view.php?id=5", corpo)
