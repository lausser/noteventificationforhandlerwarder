from notificationforwarder.baseclass import NotificationFormatter, FormattedEvent
from jinja2 import Template

class EmailFormatter(NotificationFormatter):

    def format_event(self, event):
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
            "host_name": event.eventopts.get("HOSTNAME"),
            "service_description": event.eventopts.get("SERVICEDESC", None),
        }
        event.payload = {"html": template.render(data)}
        event.summary = "mail"

