from notificationforwarder.baseclass import NotificationFormatter, FormattedEvent
from jinja2 import Template

class EmailFormatter(NotificationFormatter):

    def format_event(self, raw_event):
        event = FormattedEvent()
        email_template = """
        <html>
        <body>
            <h1>Host {{ host_name }}</h1>
{% if service_description %}
            Service {{ service_description }}
{% endif %}
        </body>
        </html>
        """
        template = Template(email_template)
        data = {
            "host_name": raw_event.get("HOSTNAME"),
            "service_description": raw_event.get("SERVICEDESC", None),
        }
        event.set_payload({"html": template.render(data)})
        event.set_summary("mail")

