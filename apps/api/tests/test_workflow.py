from apps.api.seo_ad_autopilot.analysis import Coordinator
from apps.api.seo_ad_autopilot.config import Settings
from apps.api.seo_ad_autopilot.models import (
    ApprovalDecisionRequest,
    ApprovalStatus,
    ProjectCreateRequest,
    WorkspaceBillingPolicyUpdateRequest,
    WorkspaceBillingSettlementExecutionRequest,
    RollbackActionRequest,
    SiteIntake,
)
from apps.api.seo_ad_autopilot.service import WorkflowService
from apps.api.seo_ad_autopilot.skill_registry import get_skill_registry
from apps.api.seo_ad_autopilot.skill_registry import SkillRegistry


def test_coordinator_builds_preview_bundle() -> None:
    intake = SiteIntake(
        url="https://northstar-media.example",
        site_name="Northstar Media",
        repo_url="https://github.com/example/northstar-media",
        brand_whitelist=["Northstar"],
        keywords=["editorial", "insights"],
    )
    bundle = Coordinator(get_skill_registry()).run("task_001", intake, site_id="site_001")

    assert bundle.project.project_id == "site_001"
    assert bundle.task.status.value == "awaiting_approval"
    assert bundle.plan.risk_score < 80
    assert bundle.deployment.status == "scheduled"
    assert bundle.preview.performance_budget["estimatedLcpMs"] > bundle.preview.performance_budget["baselineLcpMs"]
    assert bundle.approval_request.decision_hint


def test_high_risk_site_rejects_ads_and_blocks_auto_deploy() -> None:
    intake = SiteIntake(
        url="https://trust-clinic.example",
        site_name="Trust Clinic",
        cms_name="drupal",
        keywords=["medical guidance", "patient resources"],
    )
    bundle = Coordinator(get_skill_registry()).run("task_002", intake, site_id="site_002")

    assert bundle.opportunity_set.ad[0].title == "Do not recommend ads"
    assert bundle.plan.risk_score >= 80
    assert bundle.deployment.status == "blocked"
    assert bundle.plan.requires_manual_approval is True


def test_service_approval_promotes_and_rolls_back(isolated_service) -> None:
    service = isolated_service
    project = service.create_project(
        ProjectCreateRequest(
            name="Smoke",
            intake=SiteIntake(
                url="https://smoke.example",
                site_name="Smoke",
                repo_url="https://github.com/example/smoke",
                brand_whitelist=["Smoke"],
            ),
        )
    )
    bundle = service.run_analysis(
        project.project_id,
        SiteIntake(
            url="https://smoke.example",
            site_name="Smoke",
            repo_url="https://github.com/example/smoke",
            brand_whitelist=["Smoke"],
        ),
    )

    approved = service.approve_task(
        bundle.task.task_id,
        ApprovalDecisionRequest(decision=ApprovalStatus.approved, actor="test", note="release"),
    )

    assert approved.task.approval_status == ApprovalStatus.approved
    assert approved.deployment is not None
    assert approved.deployment.status == "deployed"

    rolled_back = service.rollback_task(bundle.task.task_id, RollbackActionRequest(actor="test", reason="cleanup"))
    assert rolled_back.rollback_bundle is not None
    assert rolled_back.rollback_bundle.commands


def test_strict_mode_blocks_deploy_without_real_market_sources(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "strict.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("SEO_AD_BOT_STRICT_PROVIDERS", "true")
    monkeypatch.setenv("SEO_AD_BOT_SKILL_REGISTRY_PATH", "packages/skill-registry/registry.json")
    settings = Settings()
    registry = SkillRegistry.load(settings.skill_registry_path)
    service = WorkflowService(settings=settings, registry=registry)
    service.database.create_all()
    project = service.create_project(
        ProjectCreateRequest(
            name="Strict Site",
            intake=SiteIntake(
                url="https://strict.example",
                site_name="Strict Site",
                repo_url="https://github.com/example/strict",
                brand_whitelist=["Strict"],
            ),
        )
    )
    bundle = service.run_analysis(
        project.project_id,
        SiteIntake(
            url="https://strict.example",
            site_name="Strict Site",
            repo_url="https://github.com/example/strict",
            brand_whitelist=["Strict"],
        ),
    )
    approved = service.approve_task(
        bundle.task.task_id,
        ApprovalDecisionRequest(decision=ApprovalStatus.approved, actor="strict-test"),
    )
    assert approved.deployment is not None
    assert approved.deployment.status in {"failed", "blocked", "scheduled"}
    if approved.deployment.status == "failed":
        assert approved.deployment.failure_code in {"STRICT_PROVIDER_BLOCKED", "PATCH_VERIFICATION_FAILED"}


def test_strict_mode_blocks_manual_settlement_without_real_ad_provider(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "strict-settlement.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("SEO_AD_BOT_STRICT_PROVIDERS", "true")
    monkeypatch.setenv("SEO_AD_BOT_SKILL_REGISTRY_PATH", "packages/skill-registry/registry.json")
    settings = Settings()
    registry = SkillRegistry.load(settings.skill_registry_path)
    service = WorkflowService(settings=settings, registry=registry)
    service.database.create_all()

    project = service.create_project(
        ProjectCreateRequest(
            name="Settlement Strict Site",
            intake=SiteIntake(
                url="https://settlement.example",
                site_name="Settlement Strict Site",
                repo_url="https://github.com/example/settlement",
                brand_whitelist=["Settlement"],
            ),
        )
    )

    service.update_billing_policy(
        WorkspaceBillingPolicyUpdateRequest(
            commercial_mode_enabled=True,
            settlement_enabled=True,
            settlement_provider_name="manual",
            settlement_account_ref="acct_001",
            settlement_payout_threshold_cents=1,
        )
    )

    result = service.execute_workspace_billing_settlement(
        WorkspaceBillingSettlementExecutionRequest(
            dry_run=False,
            provider_name="manual",
            account_ref="acct_001",
            currency="USD",
            amount_cents=5000,
            project_id=project.project_id,
        )
    )

    assert result.execution.status == "blocked"
    assert result.execution.failure_code == "SETTLEMENT_STRICT_PROVIDER_REQUIRED"
