import copy
import ast
from notificationforwarder.baseclass import NotificationFormatter

class AlertmanagerServicenowFormatter(NotificationFormatter):

    def format_event(self, event):
        event.payload = {
            "records": []
        }
        if isinstance(event.eventopts["alertmanager_payload"], str):
            event.eventopts["alertmanager_payload"] = ast.literal_eval(event.eventopts["alertmanager_payload"])
        for alert in event.eventopts["alertmanager_payload"].get("alerts", []):
            record = {}
            status = alert.get("status") or "firing"
            labels = dict((k, alert["labels"][k]) for k in alert.get("labels", {}))
            annotations = dict((k, alert["annotations"][k]) for k in alert.get("annotations", {}))
            if not labels.get("node"):
                logger.debug("event has no node "+str(alert))
                logger.debug("replace node with "+ labels.get("pod", labels.get("instance", "-no-identifier-for-node-pod-or-instance-")))
                node = labels.get("pod", labels.get("instance", "-no-identifier-for-node-pod-or-instance-"))
            else:
                node = labels["node"]
            record["source"] = "OMD_Alertmanager"
            record["event_class"] = labels.get("job", "unknown")
            record["node"] = node
            record["metric_name"] = labels["alertname"]
            record["severity"] = status
            record["description"] = annotations.get("description", "unknown")
            record["resource"] = labels.get("snow_service_name", "")
            record["additional_info"] = ""
            if labels.get("SnowServiceMap"):
                record["Name"] = labels.get("SnowServiceMap")
            if labels.get("ProductId"):
                record["ProductId"] = labels.get("ProductId")

            event.payload["records"].append(record)
        event.payload["records"] = list(tuple(event.payload["records"]))
        for record in event.payload["records"]:
            logger.info("job: {}, node: {}, alert: {}".format(record["event_class"], record["node"], record["metric_name"]))
        event.summary = "alertmanager sends {} alarms of groupKey {}".format(len(event.payload["records"]), event.eventopts["alertmanager_payload"]["groupKey"])
        if not event.payload["records"]:
            event.discard(silently=True)
