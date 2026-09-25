import type { components } from "../../api/generated";

export function conflictSummary(
  violation: components["schemas"]["Violation"],
): string {
  const facts = violation.facts ?? {};
  if (
    violation.code === "CAPACITY_BEFORE_DEADLINE" &&
    typeof facts.required_slots === "number" &&
    typeof facts.available_slots === "number"
  )
    return `${facts.required_slots * 15} minutes of required work exceed ${facts.available_slots * 15} available minutes before the deadline. Add time, revise an estimate, or explicitly change a deadline.`;
  const messages: Record<string, string> = {
    NO_CONTIGUOUS_WINDOW:
      "This task cannot fit into a supported continuous work block. Review its available windows and block-length settings.",
    PAST_DEADLINE:
      "A task deadline has already passed. Review the deadline or record its completion.",
    PROTECTED_BUSY_CONFLICT:
      "Locked or ongoing work overlaps a busy commitment. Move or unlock the work, or edit the commitment.",
    LOCK_EXCEEDS_REMAINING:
      "Protected time exceeds the remaining estimate. Review the estimate or release a lock.",
    CALENDAR_OFF_GRID:
      "A calendar event was moved outside the 15-minute grid. Review its conflict in Calendar export and connection.",
    CANCELLED_PREDECESSOR:
      "A task depends on cancelled work. Remove or revise that dependency.",
    DEPENDENCY_CYCLE:
      "The task dependencies form a cycle. Remove a dependency so the tasks can be ordered.",
    MODEL_RESOURCE_LIMIT:
      "These inputs exceed the supported computation limit. Reduce the scheduling workload and try again.",
  };
  return (
    messages[violation.code] ??
    violation.code.replaceAll("_", " ").toLowerCase()
  );
}
