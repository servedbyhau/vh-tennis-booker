import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useOverview } from "../api/queries";
import { PageTitle } from "../components/PageTitle";
import { QueryView } from "../components/QueryView";
import styles from "./HomePage.module.css";
import { BookingTicket } from "./home/BookingTicket";
import { LiveTicket } from "./home/LiveTicket";
import { SetupPanel } from "./home/SetupPanel";

/**
 * Show the next booking as a ticket that holds its settings, or the run as it goes, with the
 * Setup beside it. With several MuMu instances, the machine chosen on the ticket is the one the
 * Setup shows.
 */
export function HomePage() {
  const { t } = useTranslation();
  const overview = useOverview();
  // The machine shown, on the ticket and in the Setup alike (0: the first).
  const [machine, setMachine] = useState(0);
  return (
    <>
      <PageTitle>{t("pages.overview.title")}</PageTitle>
      <h1 className="visually-hidden">{t("pages.overview.title")}</h1>
      <div className={styles.columns}>
        <div className={styles.booking}>
          <QueryView query={overview}>
            {(data) =>
              data.running !== null && data.running.trigger !== "setup" ? (
                // A booking or a dry run: the run as it goes, in place of the choices.
                <LiveTicket runs={data.running.runs} />
              ) : (
                <BookingTicket overview={data} machine={machine} onMachine={setMachine} />
              )
            }
          </QueryView>
        </div>
        <SetupPanel machine={machine} />
      </div>
    </>
  );
}
