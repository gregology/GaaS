from app.integrations.github.check import handle as check_handle
from app.integrations.github.collect import handle as collect_handle
from app.integrations.github.classify_pr import handle as classify_pr_handle
from app.integrations.github.evaluate import handle as evaluate_handle
from app.integrations.github.act import handle as act_handle

HANDLERS = {
    "check": check_handle,
    "collect": collect_handle,
    "classify_pr": classify_pr_handle,
    "evaluate": evaluate_handle,
    "act": act_handle,
}
