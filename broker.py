import os

QUEUE = "lembretes"


def connect():
    import pika
    conn = pika.BlockingConnection(pika.URLParameters(os.environ["AMQP_URL"]))
    channel = conn.channel()
    channel.queue_declare(QUEUE, durable=True, arguments={"x-single-active-consumer": True})
    channel.queue_declare(QUEUE + ".falhas", durable=True)
    channel.queue_declare(QUEUE + ".retry", durable=True, arguments={
        "x-message-ttl": 15000, "x-dead-letter-exchange": "",
        "x-dead-letter-routing-key": QUEUE,
    })
    channel.confirm_delivery()
    return conn, channel


def publish(channel, queue, body, attempt=1):
    import pika
    channel.basic_publish("", queue, body, mandatory=True, properties=pika.BasicProperties(
        content_type="application/json", delivery_mode=2, headers={"attempt": attempt},
    ))
