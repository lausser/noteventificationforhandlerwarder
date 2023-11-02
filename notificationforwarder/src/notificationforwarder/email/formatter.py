from notificationforwarder.baseclass import NotificationFormatter, FormattedEvent
from jinja2 import Template

class EmailFormatter(NotificationFormatter):

    def format_event(self, event):
        event.payload = {}
        if "SERVICEDESC" in event.eventopts:
            event.payload["html"] = self.create_service_html(event)
            event.payload["text"] = self.create_service_text(event)
        else:
            event.payload["html"] = self.create_host_html(event)
            event.payload["text"] = self.create_host_text(event)
        event.payload["subject"] = "thesubtschek"
        event.summary = "mail"

    def create_service_html(self, event):
        email_template = """
        <html>
        <body>
            <h1>Host {{ host_name }}</h1>
            Service {{ service_description }}
        </body>
        </html>
        """
        template = Template(email_template)
        data = {
            "host_name": event.eventopts.get("HOSTNAME"),
            "service_description": event.eventopts.get("SERVICEDESC", None),
        }
        return template.render(data)

    def create_host_html(self, event):
        email_template = """
        <html>
        <body>
            <h1>Host {{ host_name }}</h1>
        </body>
        </html>
        """
        template = Template(email_template)
        data = {
            "host_name": event.eventopts.get("HOSTNAME"),
        }
        return template.render(data)

    def create_host_text(self, event):
        email_template = """
SUBJECT: *** {{ NOTIFICATIONTYPE }} *** {{ HOSTNAME }} is {{ HOSTSTATE }}
TO: {{ CONTACTEMAIL }}
Content-Type: text/plain; charset=utf-8
Content-Transfer-Encoding: 8bit
#FROM: omd@domain.com
#REPLY-TO: support@domain.com

--HOST-ALERT----------------------
- Hostname:    {{ HOSTNAME }}
- Hostaddress: {{ HOSTADDRESS }}
- - - - - - - - - - - - - - - - -
- State:       {{ HOSTSTATE }}
- Date:        {{ SHORTDATETIME }}
- Output:      {{ HOSTOUTPUT }}
{{ LONGHOSTOUTPUT }}
{% if NOTIFICATIONTYPE == 'ACKNOWLEDGEMENT' %}
----------------------------------
- Author:      {{ ACKAUTHOR }}
- Comment:     {{ ACKCOMMENT }}
----------------------------------
{% elif NOTIFICATIONCOMMENT %}
----------------------------------
- Comment:     {{ NOTIFICATIONCOMMENT }}
----------------------------------
{% else %}
----------------------------------
{% endif %}
        """
        template = Template(email_template)
        data = {
            "HOSTNAME": event.eventopts.get("HOSTNAME"),
            "HOSTADDRESS": event.eventopts.get("HOSTADDRESS"),
            "HOSTSTATE": event.eventopts.get("HOSTSTATE"),
            "HOSTOUTPUT": event.eventopts.get("HOSTOUTPUT"),
            "LONGHOSTOUTPUT": event.eventopts.get("LONGHOSTOUTPUT"),
            "NOTIFICATIONTYPE": event.eventopts.get("NOTIFICATIONTYPE"),
            "NOTIFICATIONCOMMENT": event.eventopts.get("NOTIFICATIONCOMMENT"),
            "ACKAUTHOR": event.eventopts.get("ACKAUTHOR"),
            "ACKCOMMENT": event.eventopts.get("ACKCOMMENT"),
        }
        return template.render(data)

    def create_service_text(self, event):
        email_template = """
SUBJECT: *** {{ NOTIFICATIONTYPE }} *** {{ HOSTNAME }} / {{ SERVICEDESC }} is {{ SERVICESTATE }}
TO: {{ CONTACTEMAIL }}
Content-Type: text/plain; charset=utf-8
Content-Transfer-Encoding: 8bit
#FROM: omd@domain.com
#REPLY-TO: support@domain.com

--HOST-ALERT----------------------
- Hostname:    {{ HOSTNAME }}
- Hostaddress: {{ HOSTADDRESS }}
- Service:     {{ SERVICEDESC }}
- - - - - - - - - - - - - - - - -
- State:       {{ SERVICESTATE }}
- Date:        {{ SHORTDATETIME }}
- Output:      {{ SERVICEOUTPUT }}
{{ LONGSERVICEOUTPUT }}
{% if NOTIFICATIONTYPE == 'ACKNOWLEDGEMENT' %}
----------------------------------
- Author:      {{ ACKAUTHOR }}
- Comment:     {{ ACKCOMMENT }}
----------------------------------
{% elif NOTIFICATIONCOMMENT %}
----------------------------------
- Comment:     {{ NOTIFICATIONCOMMENT }}
----------------------------------
{% else %}
----------------------------------
{% endif %}
        """
        template = Template(email_template)
        data = {
            "HOSTNAME": event.eventopts.get("HOSTNAME"),
            "SERVICEDESC": event.eventopts.get("SERVICEDESC"),
            "SERVICESTATE": event.eventopts.get("SERVICESTATE"),
            "SERVICEOUTPUT": event.eventopts.get("SERVICEOUTPUT"),
            "LONGSERVICEOUTPUT": event.eventopts.get("LONGSERVICEOUTPUT"),
            "NOTIFICATIONTYPE": event.eventopts.get("NOTIFICATIONTYPE"),
            "NOTIFICATIONCOMMENT": event.eventopts.get("NOTIFICATIONCOMMENT"),
            "ACKAUTHOR": event.eventopts.get("ACKAUTHOR"),
            "ACKCOMMENT": event.eventopts.get("ACKCOMMENT"),
        }
        return template.render(data)

