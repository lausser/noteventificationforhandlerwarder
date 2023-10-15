# noteventificationforhandlerwarder
In this framework, two aspects are in the focus. How to transport a notification to the recipient system and in which format.
In the beginning, Naemon or one of the other monitoring cores will execute a command line. The actual script and the individual command line parameters are defined in a command definition. Typical parameters are (i use the notation of Nagios macros) HOSTNAME, SERVICEDESC, SERVICESTATE, SERVICEOUTPUT. These snippets need to be put together to some kind of payload suitable for the receiving system. And then this payload must be transported to it. We call the two components *formatter* and *forwarder*. The formatter takes the raw input data and creates a payload and the forwarder transmits the payload to the destination.

Let me list some of the combinations which are usually found in enterprise environments:

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
    command_line    $USER1$/omd_notification.py \
                        --receiver victorops \
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
Your service notifications should be sent to VictorOPs (which is called Splunk On Call today, as VictorOPs was aquired by Splunk). The notification script will talk to an api and upload a a well-formatted Json payload. Therefore the notiifcation framework has two jobs. 
Take the event attributes (all the --eventopt arguments) and transform them to a Json structure.
