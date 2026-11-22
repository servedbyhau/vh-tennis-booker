import { type KeyboardEvent, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useOverview } from "../../api/queries";
import { useMachines } from "../../machines";
import { useManualTicks } from "../../manualSteps";
import { setupLeft } from "../../setupState";
import { HistoryTab } from "./HistoryTab";
import { SetupTab } from "./SetupTab";
import styles from "./SidePanel.module.css";
import { TicketsTab } from "./TicketsTab";

export type PanelTab = "tickets" | "history" | "setup";

const TABS: readonly PanelTab[] = ["tickets", "history", "setup"];

const TITLES = {
  tickets: "pages.tickets.title",
  history: "pages.history.title",
  setup: "pages.panel.setup",
} as const;

/**
 * The panel beside the ticket: the tickets booked, the History and the Setup, one tab each.
 * The Setup tab counts the tasks left in red. Arrow keys move between the tabs, as in any
 * tab list.
 */
export function SidePanel({ initialTab, machine }: { initialTab: PanelTab; machine: number }) {
  const { t } = useTranslation();
  const overview = useOverview();
  const ticks = useManualTicks();
  const machines = useMachines();
  const [tab, setTab] = useState(initialTab);
  // Kept here, so it survives opening a run, going back and changing tabs.
  const [withDry, setWithDry] = useState(false);
  /** The MuMu instance whose tickets are listed, `null` for every machine's. */
  const [ticketDevice, setTicketDevice] = useState<number | null>(null);
  const buttons = useRef<Partial<Record<PanelTab, HTMLButtonElement | null>>>({});
  const left = overview.data === undefined ? 0 : setupLeft(ticks, machines);

  function onKeyDown(event: KeyboardEvent) {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") {
      return;
    }
    const step = event.key === "ArrowRight" ? 1 : TABS.length - 1;
    const other = TABS[(TABS.indexOf(tab) + step) % TABS.length] ?? tab;
    setTab(other);
    buttons.current[other]?.focus();
  }

  return (
    <section aria-labelledby="panel-title" className={styles.panel}>
      <h2 id="panel-title" className="visually-hidden">
        {t("pages.panel.title")}
      </h2>
      <div
        role="tablist"
        aria-labelledby="panel-title"
        className={styles.tabs}
        onKeyDown={onKeyDown}
      >
        {TABS.map((name) => (
          <button
            key={name}
            ref={(button) => {
              buttons.current[name] = button;
            }}
            type="button"
            role="tab"
            id={`tab-${name}`}
            aria-selected={tab === name}
            aria-controls={`panel-${name}`}
            tabIndex={tab === name ? 0 : -1}
            className={styles.tab}
            onClick={() => setTab(name)}
          >
            {t(TITLES[name])}
            {name === "setup" && left > 0 && (
              <>
                <span aria-hidden="true" className={styles.badge}>
                  {left}
                </span>
                <span className="visually-hidden">{t("pages.panel.left", { count: left })}</span>
              </>
            )}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id={`panel-${tab}`}
        aria-labelledby={`tab-${tab}`}
        className={styles.body}
      >
        {tab === "tickets" && <TicketsTab device={ticketDevice} onDevice={setTicketDevice} />}
        {tab === "history" && <HistoryTab withDry={withDry} onWithDry={setWithDry} />}
        {tab === "setup" && <SetupTab machine={machine} />}
      </div>
    </section>
  );
}
