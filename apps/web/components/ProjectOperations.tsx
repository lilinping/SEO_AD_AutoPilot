import { ProjectConnectionTestAction } from "@/components/ProjectConnectionTestAction";
import { ProjectSyncAction } from "@/components/ProjectSyncAction";

export function ProjectOperations({ projectId }: { projectId: string }) {
  return (
    <div className="stack">
      <ProjectSyncAction projectId={projectId} />
      <ProjectConnectionTestAction projectId={projectId} />
    </div>
  );
}
