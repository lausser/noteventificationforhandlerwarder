import pika
import json
import logging
from notificationforwarder.baseclass import NotificationForwarder, NotificationFormatter, timeout


class RabbitmqForwarder(NotificationForwarder):
    def __init__(self, opts):
        super(self.__class__, self).__init__(opts)
        setattr(self, "port", int(getattr(self, "port", 5672)))
        setattr(self, "server", getattr(self, "server", "localhost"))
        setattr(self, "vhost", getattr(self, "vhost", "/"))
        setattr(self, "queue", getattr(self, "queue", "AE"))
        setattr(self, "username", getattr(self, "username", "guest"))
        setattr(self, "password", getattr(self, "password", "guest"))

        self.connected = False
        self.has_been_probed = False
        credentials = pika.PlainCredentials(self.username, self.password)
        self.connectionparameters = pika.ConnectionParameters(self.server, self.port, self.vhost, credentials)

    def probe(self):
        try:
            logger.debug("probing {}:{}".format(self.connectionparameters.host, self.connectionparameters.port))
            success = self.connect()
        except Exception as e:
            success = False
        self.has_been_probed = True
        logger.debug("probing {}:{} {}".format(self.connectionparameters.host, self.connectionparameters.port, "succeeded" if success else "failed"))
        return success

    def connect(self):
        if self.connected:
            # a previous probe was successful
            return True
        elif self.has_been_probed and not self.connected:
            # we are in submit() and a prevoius probe() has failed. give up here.
            return False
        try:
            self.connection = pika.BlockingConnection(self.connectionparameters)
            self.channel = self.connection.channel()
            self.channel.queue_declare(queue=self.queue, durable=True)
            logger.debug('connected to {}:{}'.format(
                self.connectionparameters.host,
                self.connectionparameters.port))
            self.connected = True
            return True
        except Exception as e:
            self.connected = False
            logger.critical("rabbitmq connect failed with error {}".format(e))
            return False

    def disconnect(iself):
        try:
            self.connection.close()
        except Exception as e:
            pass

    @timeout(30)
    def submit(self, event):
        if self.connect():
            try:
                self.channel = self.connection.channel()
                self.channel.queue_declare(queue=self.queue, durable=True)
                # The payload for such queueing destinations are always a list. Usually with just one element,
                # but with the potential to send multiple packets during one session.
                for single_event in event.payload:
                    self.channel.basic_publish(exchange='', routing_key=self.queue, body=json.dumps(single_event))
                return True
            except Exception as e:
                logger.critical("rabbitmq post had an exception: {} wit payload {}".format(str(e), event.summary))
                return False
        else:
            return False
    
    def __del__(self):
        self.disconnect()
