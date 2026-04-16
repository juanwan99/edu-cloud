# Re-export from new location for backwards compatibility (Task 22 cleanup)
from edu_cloud.modules.knowledge.loader import (  # noqa: F401
    load_curriculum, load_l0_blocks, load_l1_concepts, load_gaokao_index,
)
