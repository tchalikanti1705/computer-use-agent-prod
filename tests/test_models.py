from shared.models import Tenant, Task, TaskStatus

def test_tenant_creation():
    t = Tenant(name="Acme", email="a@acme.com")
    assert t.id and t.api_key.startswith("cua_") and t.is_active

def test_task_defaults():
    t = Task(instruction="test")
    assert t.status == TaskStatus.PENDING and t.total_steps == 0
