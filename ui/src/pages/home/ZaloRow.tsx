import { useState } from "react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { useLinkZalo, useSwitchZalo, useTestZalo, useUnlinkZalo } from "../../api/mutations";
import { useZalo } from "../../api/queries";
import { Button } from "../../components/Button";
import { IconButton } from "../../components/IconButton";
import { Switch } from "../../components/Switch";
import { SetupRow } from "./SetupRow";
import styles from "./SetupRow.module.css";
import zaloStyles from "./ZaloRow.module.css";

/**
 * A real run's outcome and its tickets' pictures on the user's Zalo, through their own bot: a
 * button that links it, then whom it sends to, a test message, unlinking (after a question)
 * and its switch. It shows once the backend is read.
 */
export function ZaloRow() {
  const { t } = useTranslation();
  const zalo = useZalo();
  const [linking, setLinking] = useState(false);
  const state = zalo.data;
  if (state === undefined) {
    return null;
  }
  if (!state.linked) {
    return linking ? (
      <ZaloLink onClose={() => setLinking(false)} />
    ) : (
      <SetupRow icon="send" title={t("pages.setup.zalo.title")} hint={t("pages.setup.zalo.off")}>
        <Button className={styles.small} onClick={() => setLinking(true)}>
          {t("pages.setup.zalo.link")}
        </Button>
      </SetupRow>
    );
  }
  return <ZaloLinked name={state.name ?? ""} enabled={state.enabled} />;
}

/** The linked bot: whom it sends to, and what can be done with it. */
function ZaloLinked({ name, enabled }: { name: string; enabled: boolean }) {
  const { t } = useTranslation();
  const toggle = useSwitchZalo();
  const test = useTestZalo();
  const unlink = useUnlinkZalo();
  const [asked, setAsked] = useState(false);
  const title = t("pages.setup.zalo.title");
  const failed = toggle.error ?? test.error ?? unlink.error;
  let hint = t(test.isSuccess ? "pages.setup.zalo.sent" : "pages.setup.zalo.to", { name });
  if (asked) {
    hint = t("pages.setup.zalo.ask");
  }
  return (
    <SetupRow
      icon="send"
      title={title}
      hint={hint}
      problem={failed === null || asked ? null : errorMessage(t, failed)}
    >
      {asked ? (
        <span className={styles.buttons}>
          <Button
            variant="primary"
            className={styles.small}
            onClick={() => {
              setAsked(false);
              unlink.mutate();
            }}
          >
            {t("pages.setup.zalo.yes")}
          </Button>
          <Button className={styles.small} onClick={() => setAsked(false)}>
            {t("pages.setup.zalo.no")}
          </Button>
        </span>
      ) : (
        <>
          <IconButton
            icon="send"
            label={t("pages.setup.zalo.test")}
            disabled={test.isPending}
            onClick={() => test.mutate()}
          />
          <IconButton
            icon="remove"
            label={t("pages.setup.zalo.unlink")}
            disabled={unlink.isPending}
            onClick={() => setAsked(true)}
          />
          <Switch
            label={title}
            checked={enabled}
            disabled={toggle.isPending}
            onChange={(on) => toggle.mutate(on)}
          />
        </>
      )}
    </SetupRow>
  );
}

/** How to make a bot and write to it, then its token pasted; the backend finds the chat. */
function ZaloLink({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const link = useLinkZalo();
  const [token, setToken] = useState("");
  const ready = token.trim().length >= 8 && !link.isPending;
  return (
    <form
      className={zaloStyles.form}
      aria-label={t("pages.setup.zalo.title")}
      onSubmit={(event) => {
        event.preventDefault();
        if (ready) {
          link.mutate(token.trim());
        }
      }}
    >
      <span className={styles.title}>{t("pages.setup.zalo.title")}</span>
      <ol className={zaloStyles.steps}>
        <li>{t("pages.setup.zalo.step1")}</li>
        <li>{t("pages.setup.zalo.step2")}</li>
        <li>{t("pages.setup.zalo.step3")}</li>
      </ol>
      <label className={zaloStyles.field}>
        <span className={zaloStyles.label}>{t("pages.setup.zalo.token")}</span>
        <input
          type="password"
          autoComplete="off"
          spellCheck={false}
          value={token}
          onChange={(event) => setToken(event.target.value)}
        />
      </label>
      {link.isError && (
        <span role="alert" className={styles.problem}>
          {errorMessage(t, link.error)}
        </span>
      )}
      <span className={styles.buttons}>
        <Button type="submit" variant="primary" className={styles.small} disabled={!ready}>
          {t(link.isPending ? "pages.setup.zalo.linking" : "pages.setup.zalo.link")}
        </Button>
        <Button className={styles.small} disabled={link.isPending} onClick={onClose}>
          {t("pages.setup.zalo.cancel")}
        </Button>
      </span>
    </form>
  );
}
