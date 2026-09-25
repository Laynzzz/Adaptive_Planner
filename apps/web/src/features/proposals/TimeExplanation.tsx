import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { request } from "../../api/client";
import type { components } from "../../api/generated";

export default function TimeExplanation({
  path,
  taskNames,
}: {
  path: string;
  taskNames: Record<string, string>;
}) {
  const [open, setOpen] = useState(false);
  const inputs = useQuery({
    queryKey: ["time-inputs", path],
    queryFn: () => request<components["schemas"]["TimeInputView"]>(path),
    enabled: open,
  });
  function name(field: string) {
    const parts = field.split(".");
    if (parts[0] === "task")
      return `${taskNames[parts[1]] ?? "Task"}: ${parts.slice(2).join(" ").replaceAll("_", " ")}`;
    return field.replaceAll("_", " ").replaceAll(".", " ");
  }
  return (
    <details
      onToggle={(event) => setOpen(event.currentTarget.open)}
      className="evidence-report"
    >
      <summary>Original times and planning adjustments</summary>
      <p className="field-help">
        The planner uses 15-minute slots. Available windows round inward; busy
        time rounds outward. This can make a very tight schedule infeasible.
        Times below retain their explicit offsets.
      </p>
      {open && inputs.isPending && (
        <p role="status">Loading original inputs…</p>
      )}
      {inputs.isError && (
        <p role="alert">
          Original inputs could not be loaded.{" "}
          <button onClick={() => void inputs.refetch()}>Retry</button>
        </p>
      )}
      {inputs.data && (
        <>
          {(inputs.data.rounding_losses?.length ?? 0) === 0 ? (
            <p>No time rounding was needed.</p>
          ) : (
            <div className="evidence-scroll">
              <table>
                <caption>Adjustments for this planning snapshot</caption>
                <thead>
                  <tr>
                    <th>Input</th>
                    <th>Original time</th>
                    <th>Used for planning</th>
                    <th>Difference</th>
                  </tr>
                </thead>
                <tbody>
                  {inputs.data.rounding_losses?.map((loss, index) => (
                    <tr key={index}>
                      <th>{name(loss.field)}</th>
                      <td>{loss.original}</td>
                      <td>{loss.rounded}</td>
                      <td>{Number((loss.seconds / 60).toFixed(2))} minutes</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <details>
            <summary>All original time inputs</summary>
            <ul>
              {inputs.data.original_time_inputs?.map((input, index) => (
                <li key={index}>
                  {name(input.field)}: {input.value} ({input.timezone}
                  {input.fold !== null && input.fold !== undefined
                    ? `, repeated-hour choice ${input.fold}`
                    : ""}
                  )
                </li>
              ))}
            </ul>
          </details>
        </>
      )}
    </details>
  );
}
