"""R.02 explicit grant and permission rows, each inserted just before first use.

One function per driver step, called in STEPS order, which is the order the
tests/lifecycle chains provision them. Every row equals the named
tests/lifecycle provision() helper field-for-field; component identities,
provider configuration and hashes are imported from the packages, never copied.
Production composition creates none of these grants (docs/35), there is no HTTP
grant endpoint (docs/29), and inserting them all up front is untested, so the
driver never does that. synthetic_demo is only the FixedProposalPolicy.grant
argument; lifecycle_authorities has no such column.
"""
from returnops_domain import lifecycle_tables as life
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.investigation_policy import InvestigationPolicy
from returnops_domain.label_artifact_sources import (COMPONENT as ARTIFACT_COMPONENT, CONFIG as ARTIFACT_CONFIG,
    profile_hash)
from returnops_domain.label_artifact_tables import permissions as artifact_permissions
from returnops_domain.label_execution_sources import (COMPONENT as LABEL_COMPONENT, CONFIG as LABEL_CONFIG,
    config_hash as label_config_hash)
from returnops_domain.label_execution_tables import permissions as label_permissions
from returnops_domain.label_pdf import PDF_PROFILE_ID
from returnops_domain.notification_intent import RETURN_PRODUCER
from returnops_domain.notification_profile import COMPONENT as NOTIFICATION_COMPONENT
from returnops_domain.pass_review_sources import COMPONENT as REVIEW_COMPONENT
from returnops_domain.preview_profile import APPROVAL_COMPONENT, COMPONENT as PREVIEW_COMPONENT
from returnops_domain.proposal_policy import COMPONENT as PROPOSAL_COMPONENT, FixedProposalPolicy
from returnops_domain.return_execution_sources import (COMPONENT as RETURN_COMPONENT, CONFIG as RETURN_CONFIG,
    config_hash as return_config_hash)
from returnops_domain.return_execution_tables import permissions as return_permissions

# Provision-time policies first, then the private chain in test order.
PROVISION = ('order_investigation', 'fixed_proposal')
STEPS = ('review', 'preview_and_approval', 'execution', 'create_return', 'generate_label',
         'label_artifact', 'notification')
_SUMMARY = ('store_id', 'component_id', 'purpose', 'provider_id', 'config_id', 'command_type', 'pdf_profile_id',
            'revision', 'enabled')


def _authority(store, component, purpose):
    return life.authorities, dict(store_id=store, component_id=component, purpose=purpose, revision=1, enabled=True)


def review_rows(store):
    """pass_review_helpers.provision_review: REVIEW for the controlled PASS receiver."""
    return [_authority(store, REVIEW_COMPONENT, 'REVIEW')]


def preview_and_approval_rows(store):
    """approve_helpers.provision: PREVIEW then APPROVAL; EXECUTION stays absent."""
    return [_authority(store, PREVIEW_COMPONENT, 'PREVIEW'), _authority(store, APPROVAL_COMPONENT, 'APPROVAL')]


def execution_rows(store):
    """approval_admission_helpers.provision_execution: EXECUTION only after APPROVE."""
    return [_authority(store, APPROVAL_COMPONENT, 'EXECUTION')]


def create_return_rows(store):
    """create_return_execution_helpers.provision: after preparation, before CREATE_RETURN."""
    return [_authority(store, RETURN_COMPONENT, 'EXECUTION'), _authority(store, RETURN_COMPONENT, 'EFFECT'),
            (return_permissions, dict(store_id=store, component_id=RETURN_COMPONENT,
                provider_id=RETURN_CONFIG['provider_id'], config_id=RETURN_CONFIG['config_id'],
                command_type=RETURN_CONFIG['command_type'], config_hash=return_config_hash(), revision=1,
                create_enabled=True, query_enabled=True))]


def generate_label_rows(store):
    """label_execution_helpers.provision: after the return-source bridge, before GENERATE_LABEL."""
    return [_authority(store, LABEL_COMPONENT, 'EXECUTION'), _authority(store, LABEL_COMPONENT, 'EFFECT'),
            (label_permissions, dict(store_id=store, component_id=LABEL_COMPONENT,
                provider_id=LABEL_CONFIG['provider_id'], config_id=LABEL_CONFIG['config_id'],
                command_type=LABEL_CONFIG['command_type'], config_hash=label_config_hash(), revision=1,
                create_enabled=True, query_enabled=True))]


def label_artifact_rows(store):
    """label_artifact_helpers.provision: EFFECT and the PDF profile row, after the label fact."""
    return [_authority(store, ARTIFACT_COMPONENT, 'EFFECT'),
            (artifact_permissions, dict(store_id=store, component_id=ARTIFACT_COMPONENT,
                provider_id=ARTIFACT_CONFIG['provider_id'], config_id=ARTIFACT_CONFIG['config_id'],
                pdf_profile_id=PDF_PROFILE_ID, profile_hash=profile_hash(), revision=1,
                read_existing_enabled=True, store_enabled=True))]


def notification_rows(store):
    """notification_helpers.provision: NOTIFICATION then OUTCOME, after the label artifact."""
    return [_authority(store, NOTIFICATION_COMPONENT, 'NOTIFICATION'), _authority(store, RETURN_PRODUCER, 'OUTCOME')]


def _insert(engine, rows):
    # A plain insert: an existing row fails the step instead of being reused.
    with CustomerUnitOfWork(engine, write=True) as uow:
        for table, values in rows:
            uow.execute(table.insert().values(**values))
        uow.commit()
    return [dict(table=table.name, **{name: values[name] for name in _SUMMARY if name in values})
            for table, values in rows]


def review(engine, store):
    return _insert(engine, review_rows(store))


def preview_and_approval(engine, store):
    return _insert(engine, preview_and_approval_rows(store))


def execution(engine, store):
    return _insert(engine, execution_rows(store))


def create_return(engine, store):
    return _insert(engine, create_return_rows(store))


def generate_label(engine, store):
    return _insert(engine, generate_label_rows(store))


def label_artifact(engine, store):
    return _insert(engine, label_artifact_rows(store))


def notification(engine, store):
    return _insert(engine, notification_rows(store))


def order_investigation(engine, store, catalogue):
    """demo.py --order-investigation, with the deterministic cups catalogue."""
    policy = InvestigationPolicy(engine)
    policy.configure(store, catalogue=catalogue)
    policy.grant(store, catalogue.metadata.provider_id, can_read=True)
    metadata = catalogue.metadata
    return [dict(table='investigation_services', store_id=store, provider_id=metadata.provider_id,
                 dataset_version=metadata.dataset_version, dataset_sha256=metadata.dataset_sha256),
            dict(table='investigation_provider_grants', store_id=store, provider_id=metadata.provider_id, can_read=True)]


def fixed_proposal(engine, store):
    """demo.py --fixed-proposal: the existing PROPOSAL purpose, explicit synthetic opt-in."""
    FixedProposalPolicy(engine).grant(store, synthetic_demo=True, enabled=True)
    return [dict(table=life.authorities.name, store_id=store, component_id=PROPOSAL_COMPONENT, purpose='PROPOSAL',
                 enabled=True)]
