import pika
import json
import logging
from notificationforwarder.baseclass import NotificationForwarder, NotificationFormatter, timeout


class Rabbitmq(NotificationForwarder):
    def __init__(self, opts):
        super(self.__class__, self).__init__(opts)
        setattr(self, "port", int(getattr(self, "port", 5672)))
        setattr(self, "server", getattr(self, "server", "localhost"))
        setattr(self, "vhost", getattr(self, "vhost", "/"))
        setattr(self, "queue", getattr(self, "queue", "AE"))
        setattr(self, "username", getattr(self, "username", "guest"))
        setattr(self, "password", getattr(self, "password", "guest"))

        credentials = pika.PlainCredentials(self.username, self.password)
        self.connectionparameters = pika.ConnectionParameters(self.server, self.port, self.vhost, credentials)

    def connect(self):
        try:
            self.connection = pika.BlockingConnection(self.connectionparameters)
            self.channel = self.connection.channel()
            self.channel.queue_declare(queue=self.queue, durable=True)
            logger.debug('Connected to {}:{}'.format(
                self.connectionparameters.host,
                self.connectionparameters.port))
            return True
        except Exception as e:
            logger.critical("connect said: "+ str(e))
            return False

    def disconnect():
        try:
            self.connection.close()
        except Exception as e:
            pass

    @timeout(30)
    def submit(self, payload):
        if self.connect():
            try:
                logger.info("submit "+payload)
                self.channel = self.connection.channel()
                self.channel.queue_declare(queue=self.queue, durable=True)
                for event in payload:
                    if "service_description" in event:
                        logger.info("host: {}, service: {}, state: {}, output: {}".format(event["host_name"], event["service_description"], event["state"], event["output"]))
                    else:
                        logger.info("host: {}, state: {}, output: {}".format(event["host_name"], event["state"], event["output"]))
                    logger.debug(json.dumps(event))
                    self.channel.basic_publish(exchange='', routing_key=MQQUEUE, body=json.dumps(event))
                return True
            except Exception as e:
                logger.critical("rabbitmq post had an exception: {} wit payload {}".format(str(e), str(payload)))
                return False
    

