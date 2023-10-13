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



