import { type KeyboardEvent, useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { errorMessage } from "../../api/errors";
import { useAttachAccount, useDetachAccount } from "../../api/mutations";
import { useCustomers } from "../../api/queries";
import type { Customer, CustomerAccount } from "../../api/types";
import { Button } from "../../components/Button";
import { Icon, type IconName } from "../../components/Icon";
import { QueryView } from "../../components/QueryView";
import { accountOn, useMachines } from "../../machines";
import { paths } from "../../paths";
import { useReadiness } from "../../readiness";
import styles from "./AccountPicker.module.css";
import { machineName } from "./ticketText";

interface ChoiceProps {
  icon: IconName;
  title: string;
  phone?: string;
  label?: string;
  /** Where it is now, on another machine. */
  place?: string;
  chosen: boolean;
  disabled: boolean;
  onPick: () => void;
}

/** One line to choose: who, the account, and a tick in place of the icon once chosen. */
function Choice(props: ChoiceProps) {
  const { icon, title, phone, label, place, chosen, disabled, onPick } = props;
  return (
    <button
      type="button"
      aria-pressed={chosen}
      title={[title, phone, label].filter(Boolean).join(" · ")}
      disabled={disabled}
      className={styles.choice}
      onClick={onPick}
    >
      <span className={styles.avatar}>
        <Icon name={chosen ? "check" : icon} />
      </span>
      <span className={styles.text}>
        <span className={styles.name}>{title}</span>
        {phone !== undefined && <AccountLine phone={phone} label={label} />}
      </span>
      {place !== undefined && <span className={styles.place}>{place}</span>}
    </button>
  );
}

/** An account in a line: its phone number, then its name if it has one. */
function AccountLine({ phone, label }: { phone: string; label?: string }) {
  return (
    <span className={styles.hint}>
      <span className={styles.phone}>{phone}</span>
      {label !== undefined && label !== "" && ` · ${label}`}
    </span>
  );
}

interface PickerProps {
  customers: readonly Customer[];
  mumuIndex: number;
}

/** The account in use as a button, and under it, once pressed, every one to choose from. */
function Picker({ customers, mumuIndex }: PickerProps) {
  const { t } = useTranslation();
  const id = useId();
  const machines = useMachines();
  const { accountless } = useReadiness();
  const attach = useAttachAccount();
  const detach = useDetachAccount();
  const button = useRef<HTMLButtonElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  /** The account of another machine asked about, before it moves here. */
  const [asked, setAsked] = useState<CustomerAccount | null>(null);
  const attached = accountOn(customers, mumuIndex);
  const pending = attach.isPending || detach.isPending;
  const error = attach.error ?? detach.error;

  // The list may open below the edge of the panel.
  useEffect(() => {
    if (open) {
      list.current?.scrollIntoView?.({ block: "nearest" });
    }
  }, [open, asked]);

  function close() {
    setOpen(false);
    setAsked(null);
    button.current?.focus();
  }

  function toggle() {
    attach.reset();
    detach.reset();
    setAsked(null);
    setOpen(!open);
  }

  function pickNone() {
    attach.reset();
    if (attached === null) {
      close();
    } else {
      detach.mutate(mumuIndex, { onSuccess: close });
    }
  }

  function move(account: CustomerAccount) {
    detach.reset();
    attach.mutate({ mumuIndex, accountId: account.id }, { onSuccess: close });
  }

  function pick(account: CustomerAccount) {
    if (account.device === mumuIndex) {
      close();
    } else if (account.device === null) {
      move(account);
    } else {
      // The machine it is on would be left without: asked first.
      setAsked(account);
    }
  }

  function onKeyDown(event: KeyboardEvent) {
    if (event.key === "Escape" && open) {
      close();
    }
  }

  /** It books tomorrow with nobody chosen: the one thing to do here. */
  const remind = accountless.some((machine) => machine.mumuIndex === mumuIndex);
  const choices = customers.flatMap((customer) =>
    customer.accounts.map((account) => ({ customer, account })),
  );
  return (
    <div onKeyDown={onKeyDown}>
      <button
        ref={button}
        type="button"
        aria-expanded={open}
        aria-controls={`${id}-list`}
        className={remind ? `${styles.current} ${styles.remind}` : styles.current}
        onClick={toggle}
      >
        <span className={attached === null ? `${styles.avatar} ${styles.empty}` : styles.avatar}>
          <Icon name="person" />
        </span>
        <span className={styles.text}>
          <span className="visually-hidden">{t("pages.setup.account.title")}: </span>
          <span className={styles.name}>
            {attached?.customer.name ?? t("pages.setup.account.empty")}
          </span>
          {attached === null ? (
            <span className={styles.hint}>{t("pages.setup.account.emptyHint")}</span>
          ) : (
            <AccountLine phone={attached.account.phone ?? ""} label={attached.account.label} />
          )}
        </span>
        <span className={styles.chevron}>
          <Icon name="choose" />
        </span>
      </button>
      {error !== null && (
        <p role="alert" className={styles.error}>
          {errorMessage(t, error)}
        </p>
      )}
      <div
        ref={list}
        id={`${id}-list`}
        role="group"
        aria-label={t("pages.setup.account.title")}
        hidden={!open}
        className={styles.list}
      >
        {open && (
          <>
            {choices.map(({ customer, account }) => (
              <div
                key={account.id}
                className={
                  asked?.id === account.id ? `${styles.item} ${styles.asked}` : styles.item
                }
              >
                <Choice
                  icon="person"
                  title={customer.name}
                  phone={account.phone ?? t("pages.customers.noLogin")}
                  label={account.label}
                  place={
                    account.device === null || account.device === mumuIndex
                      ? undefined
                      : t("pages.setup.account.onMachine", {
                          machine: machineName(t, machines, account.device),
                        })
                  }
                  chosen={account.device === mumuIndex}
                  disabled={pending || account.phone === null}
                  onPick={() => pick(account)}
                />
                {asked?.id === account.id && account.device !== null && (
                  <div className={styles.move}>
                    <p>
                      {t("pages.setup.account.move", {
                        from: machineName(t, machines, account.device),
                        to: machineName(t, machines, mumuIndex),
                      })}
                    </p>
                    <div className={styles.moveButtons}>
                      <Button
                        variant="primary"
                        disabled={pending}
                        className={styles.small}
                        onClick={() => move(account)}
                      >
                        {t("pages.setup.account.moveYes")}
                      </Button>
                      <Button className={styles.small} onClick={() => setAsked(null)}>
                        {t("pages.setup.account.moveNo")}
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            ))}
            {choices.length > 0 && (
              <div className={styles.item}>
                <Choice
                  icon="none"
                  title={t("pages.setup.account.none")}
                  chosen={attached === null}
                  disabled={pending}
                  onPick={pickNone}
                />
              </div>
            )}
            <Link to={paths.management} className={styles.manage}>
              {t("pages.setup.account.manage")}
              <Icon name="go" />
            </Link>
          </>
        )}
      </div>
    </div>
  );
}

/**
 * The customer's account a machine books with: each run checks that the machine's Vinhomes app
 * is logged in with it, and changes it if not.
 */
export function AccountPicker({ mumuIndex }: { mumuIndex: number }) {
  const customers = useCustomers();
  return (
    <QueryView query={customers}>
      {(list) => <Picker customers={list} mumuIndex={mumuIndex} />}
    </QueryView>
  );
}
