import { useCustomers, useKeepOn, useOverview, useSetupReport } from "./api/queries";
import { useMachines } from "./machines";
import { type SetupFacts, STEPS, type StepId, stepsDone } from "./setupSteps";

/**
 * Gather what the Setup's steps are told from and whether each is done. `background` is the
 * header's use: the checks, which ask MuMu, are read when the app opens and every 15 minutes, not
 * on each focus as on the Setup page. `left` is the steps not done, `null` until all is read.
 */
export function useSetupSteps(background = false) {
  const report = useSetupReport(background);
  const keepOn = useKeepOn();
  const customers = useCustomers();
  const overview = useOverview();
  const machines = useMachines();
  const facts: SetupFacts = {
    keepOn: keepOn.data?.on,
    report: report.data,
    machines,
    customers: customers.data,
    daily: overview.data?.schedule.enabled,
  };
  const done = stepsDone(facts);
  const read = report.isFetched && keepOn.isFetched && customers.isFetched && overview.isFetched;
  const left: StepId[] | null =
    report.data === undefined || !read ? null : STEPS.filter((step) => !done[step]);
  return { report, overview, facts, done, read, left };
}
