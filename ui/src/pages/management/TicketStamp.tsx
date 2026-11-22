import { useTranslation } from "react-i18next";
import type { Ticket } from "../../api/types";
import { Stamp } from "../../components/Stamp";

const TONES = {
  registered: "booked",
  processing: "muted",
  cancelled: "failed",
  other: "muted",
} as const;

/** A ticket's status as a small stamp; one not known here in the app's own words. */
export function TicketStamp({ ticket }: { ticket: Pick<Ticket, "status" | "status_text"> }) {
  const { t } = useTranslation();
  return (
    <Stamp tone={TONES[ticket.status]} size="small">
      {ticket.status === "other" ? ticket.status_text : t(`pages.tickets.status.${ticket.status}`)}
    </Stamp>
  );
}
