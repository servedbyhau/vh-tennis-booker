import { type KeyboardEvent, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { errorMessage } from "../../api/errors";
import { useAttachAccount, useDetachAccount } from "../../api/mutations";
import { useCustomers } from "../../api/queries";
import type { Customer, CustomerAccount } from "../../api/types";
import { Button } from "../../components/Button";
import { Icon } from "../../components/Icon";
import { QueryView } from "../../components/QueryView";
import { accountOn, useMachines } from "../../machines";
import { paths } from "../../paths";
import styles from "./AccountPicker.module.css";
import { machineName } from "./ticketText";

interface ChoiceProps {
  title: string;
  hint?: string;
  /** The machine that books with it now, if another one. */
  machine?: string;
  chosen: boolean;
  disabled: boolean;
  onPick: () => void;
}

function Choice({ title, hint, machine, chosen, disabled, onPick }: ChoiceProps) {
  const { t } = useTranslation();
  return (
    <button
      type="button"
      aria-pressed={chosen}
      disabled={disabled}
      className={styles.choice}
      onClick={onPick}
    >
      <span className={styles.tick}>{chosen && <Icon name="check" />}</span>
      <span className={styles.text}>
        <span className={styles.name}>{title}</span>
        {hint !== undefined && hint !== "" && <span className={styles.hint}>{hint}</span>}
      </span>
      {machine !== undefined && (
        <span className={styles.machine}>{t("pages.setup.account.onMachine", { machine })}</span>
      )}
    </button>
  );
}

interface PickerProps {
  customers: readonly Customer[];
  mumuIndex: number;
}

/** The account in use as a button, and under it, once pressed, every account to pick from. */
function Picker({ customers, mumuIndex }: PickerProps) {
  const { t } = useTranslation();
  const id = useId();
  const machines = useMachines();
  const attach = useAttachAccount();
  const detach = useDetachAccount();
  const button = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  /** The account of another machine asked about, before it moves here. */
  const [asked, setAsked] = useState<CustomerAccount | null>(null);
  const attached = accountOn(customers, mumuIndex);
  const pending = attach.isPending || detach.isPending;
  const error = attach.error ?? detach.error;

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

  const withAccounts = customers.filter((customer) => customer.accounts.length > 0);
  return (
    <div className={styles.picker} onKeyDown={onKeyDown}>
      <button
        ref={button}
        type="button"
        aria-expanded={open}
        aria-controls={`${id}-list`}
        className={styles.current}
        onClick={toggle}
      >
        <span className={styles.avatar}>
          <Icon name="person" />
        </span>
        <span className={styles.text}>
          <span className="visually-hidden">{t("pages.setup.account.title")}: </span>
          <span className={styles.name}>
            {attached?.customer.name ?? t("pages.setup.account.empty")}
          </span>
          <span className={styles.hint}>
            {attached === null
              ? t("pages.setup.account.noneHint")
              : [attached.account.phone, attached.account.label].filter(Boolean).join(" · ")}
          </span>
        </span>
        <span className={styles.chevron}>
          <Icon name="down" />
        </span>
      </button>
      {error !== null && (
        <p role="alert" className={styles.error}>
          {errorMessage(t, error)}
        </p>
      )}
      <div
        id={`${id}-list`}
        role="group"
        aria-label={t("pages.setup.account.title")}
        hidden={!open}
        className={styles.list}
      >
        {open && (
          <>
            {withAccounts.map((customer) => (
              <div
                key={customer.id}
                role="group"
                aria-labelledby={`${id}-${customer.id}`}
                className={styles.customer}
              >
                <span id={`${id}-${customer.id}`} className={styles.customerName}>
                  {customer.name}
                </span>
                {customer.accounts.map((account) => (
                  <div key={account.id}>
                    <Choice
                      title={account.phone ?? t("pages.customers.noLogin")}
                      hint={account.label}
                      machine={
                        account.device === null || account.device === mumuIndex
                          ? undefined
                          : machineName(t, machines, account.device)
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
              </div>
            ))}
            <div className={styles.customer}>
              <Choice
                title={t("pages.setup.account.none")}
                hint={t("pages.setup.account.noneHint")}
                chosen={attached === null}
                disabled={pending}
                onPick={pickNone}
              />
              <Link to={paths.management} className={styles.add}>
                <span className={styles.tick}>
                  <Icon name="add" />
                </span>
                {t("pages.setup.account.add")}
              </Link>
            </div>
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
