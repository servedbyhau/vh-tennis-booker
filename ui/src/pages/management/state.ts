import { useOutletContext } from "react-router";

/** What the sections keep while another one shows. */
export interface ManagementState {
  /** Whether the History lists dry runs too. */
  withDry: boolean;
  onWithDry: (on: boolean) => void;
  /** The customer whose tickets are listed, `null` for every customer's. */
  customer: string | null;
  onCustomer: (customer: string | null) => void;
}

/** Read what the management page keeps for its sections. */
export function useManagement(): ManagementState {
  return useOutletContext<ManagementState>();
}
