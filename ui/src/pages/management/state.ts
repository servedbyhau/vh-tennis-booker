import { useOutletContext } from "react-router";

/** What the sections keep while another one shows. */
export interface ManagementState {
  /** Whether the History lists dry runs too. */
  withDry: boolean;
  onWithDry: (on: boolean) => void;
  /** The MuMu instance whose tickets are listed, `null` for every machine's. */
  device: number | null;
  onDevice: (device: number | null) => void;
}

/** Read what the management page keeps for its sections. */
export function useManagement(): ManagementState {
  return useOutletContext<ManagementState>();
}
