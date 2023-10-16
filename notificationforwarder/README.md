# noteventificationforhandlerwarder
In this framework, two aspects are in the focus. How to transport a notification to the recipient system and in which format.
In the beginning, Naemon or one of the other monitoring cores will execute a command line. The actual script and the individual command line parameters are defined in a command definition. Typical parameters are (i use the notation of Nagios macros) HOSTNAME, SERVICEDESC, SERVICESTATE, SERVICEOUTPUT. These snippets need to be put together to some kind of payload suitable for the receiving system. And then this payload must be transported to it. We call the two components *formatter* and *forwarder*. The formatter takes the raw input data and creates a payload and the forwarder transmits the payload to the destination.
What the framework does for you behind the scenes. When forwarding to a recipient fails, the event is saved in a local sqlite database for a certain time and re-sent when the script is called next time and the recipient is available again. Logging of successful and of course faile deliveries is also done automatically.

Let me list some of the formatter/forwarder combinations which are usually found in enterprise environments:

|formatter     |forwarder |
|--------------|----------|
|plain text    |smtp      |
|html          |smtp      |
|json          |ServiceNow api|
|json          |Remedy api|
|json          |SMS gateway api|
|line of text  |Syslog |
|json          |Splunk HEC |
|json          |RabbitMQ |

Of course json is not json, the format is different depending on the recipient.


For every notification recipient you need such a pair, practically it means, you have to write two python files. 
Imagine you have a command definition like this:
```
define command{
    command_name    notify-service-victorops
    command_line    $USER1$/notificationforwarder \
                        --receiver myspecialreceiver \
                        --receiveropt company_id='$_CONTACTCOMPANY_ID$' \
                        --receiveropt company_key='$_CONTACTCOMPANY_KEY$' \
                        --receiveropt routing_key='$_CONTACTROUTING_KEY$' \
...
                        --eventopt HOSTNAME='$HOSTNAME$' \
                        --eventopt HOSTSTATE='$HOSTSTATE$' \
                        --eventopt HOSTADDRESS='$HOSTADDRESS$' \
                        --eventopt SERVICEDESC='$SERVICEDESC$' \
                        --eventopt SERVICESTATE='$SERVICESTATE$' \
                        --eventopt SERVICEOUTPUT='$SERVICEOUTPUT$' \
                        --eventopt LONGSERVICEOUTPUT='$LONGSERVICEOUTPUT$' \
                    >> $USER4$/var/log/notificationforwarder_victorops.log 2>&1
}
```
Your service notifications should be sent to some ticket tool. The notification script will talk to a REST api and upload a a well-formatted Json payload. Therefore the notifcation framework has two jobs. 
First, take the event attributes (all the --eventopt arguments) and transform them to a Json structure. Then, upload it with a POST request.

In your OMD site you create a folder *~/local/lib/python/notificationforwarder/myspecialreceiver* and add two files, *formatter.py* and forwarder.py.
A skeleton for the *formatter.py* looks like this:

```python
import time
import os
from notificationforwarder.baseclass import NotificationFormatter, FormattedEvent

class MyspecialreceiverFormatter(NotificationFormatter):

    def format_event(self, event):
        json_payload = {}
        # fill the payload with whatever is required
        json_payload['hostname'] = event.eventopts['HOSTNAME']
        json_payload['remark'] = "here is a ticket for you, haha"
       
        event.payload = json_payload
        event.summary = "this is a one-line summary which will be used to write a log"
```
The class name has to be the argument of the *\-\-receiver* parameter with the first letter in upper case plus "Formatter". It must have a method *format_event*. This method is called with an event object, which has an attribute event.eventopts. This is a dictionary where keys and values are taken from the *\-\-eventopt* parameters of the **$USER1$/notificationforwarder** command. The method shall shall set the attributes *payload* and *summary* of the event object.

A skeleton for the *forwarder.py* looks like this:

```
import json
import requests
import os
from notificationforwarder.baseclass import NotificationForwarder, NotificationF
ormatter, timeout

class MyspecialreceiverForwarder(NotificationForwarder):
    def __init__(self, opts):
        super(self.__class__, self).__init__(opts)
        self.url = "https://alert.someapi.com/v1/tickets/"+self.company_id+"/alert/"+self.company_key+"/"+self.routing_key

    @timeout(30)
    def submit(self, event):
        try:
            logger.info("submit "+event.summary)
            response = requests.post(self.url, json=event.payload)
            if response.status_code != 200:
                logger.critical("POST returned "+str(response.status_code)+" "+response.text)
                return False
            else:
                logger.debug("POST returned "+str(response.status_code)+" "+response.text)
                return True
        except Exception as e:
            logger.critical("POST had an exception: {}".format(str(e)))
            return False

    def probe(self):
        r = requests.head(self.url)
        return r.status_code == 200
```

Again, the class name has to be the argument of the *\-\-receiver* parameter with the first letter in upper case, but this time with "Forwarder" appended. This class must have a method *submit()*, which gets the event object which was supplied with payload and summary in the formatting step. If submit() returns a False value, the framework will spool the event in a database.
The next time Naemon is executing the notificationforwarder script for this receiver, it will try to submit the events which have been spooled so far. If the Forwarder class has an optional method *probe()*, it will check if the receiver is now up again before it flushes the spooled events.


