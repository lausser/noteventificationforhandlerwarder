import getpass
import smtplib
from email.mime.text import MIMEText
from notificationforwarder.baseclass import NotificationForwarder, NotificationFormatter, timeout

class Email(NotificationForwarder):
    def __init__(self, opts):
        super(self.__class__, self).__init__(opts)
        setattr(self, "smtp_server", getattr(self, "smtp_server", "localhost"))
        setattr(self, "smtp_port", int(getattr(self, "smtp_port", 25)))
        setattr(self, "sender", getattr(self, "sender", None))
        setattr(self, "recipient", getattr(self, "recipient", None))

    @timeout(30)
    def submit(self, payload):
        try:
            message = MIMEMultipart()
            message['From'] = getpass.getuser()
            message['To'] = self.recipient
            message['Subject'] = payload["subject"]
            if "html" in payload:
                message.attach(MIMEText(payload["html"], "html"))
            elif "text" in payload:
                message.attach(MIMEText(payload["text"], "text"))
            else:
                message.attach(MIMEText("formatter must return html or text", "text"))
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.sendmail(self.sender, self.recipient, message.as_string())
            server.quit()
            return True
        except Exception as e:
            logging.critical("sending mail failed: {}".format(str(e)))
            return False

