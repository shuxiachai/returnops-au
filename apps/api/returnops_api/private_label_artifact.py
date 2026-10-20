"""Private explicit composition. No default worker, route or grant registration."""
from returnops_domain.label_artifact import LabelArtifactService
from .customer_authority import CurrentRequestAuthority

def compose_private_label_artifact(engine,auth_config,authorization,**options):
    return LabelArtifactService(engine,CurrentRequestAuthority(auth_config,authorization),**options)
