import { useT } from "../../i18n";
import type { ProposedAction } from "../../types/recommendation";
import { CARD, BTN_PRIMARY, BTN_SECONDARY } from "../../ui";

type ApprovalPageProps = {
  action: ProposedAction;
  onConfirm: () => void;
  onCancel: () => void;
};

export function ApprovalPage({ action, onConfirm, onCancel }: ApprovalPageProps) {
  const t = useT();
  return (
    <div className="flex flex-col gap-6 py-4 rise-in">
      <div>
        <p className="text-sm font-semibold text-brand-red uppercase tracking-wide m-0 mb-2">
          {t("approval.proposedAction")}
        </p>
        <h1 className="text-3xl font-bold leading-tight text-ink m-0">{action.title}</h1>
      </div>

      <div className={`${CARD} p-5 flex flex-col gap-4`}>
        <div>
          <p className="text-xs font-bold text-gray-500 uppercase tracking-wide m-0 mb-1">{t("approval.whatThisMeans")}</p>
          <p className="text-sm text-gray-700 leading-relaxed m-0">{action.description}</p>
        </div>
        <div className="border-t border-gray-100 pt-4">
          {/* action.consequence states plainly what DOES change once confirmed (e.g. "Your
              BahnCard 50 will be cancelled and BahnCard 25 will start in its place") — both
              producers of this field write it that way, and the yellow note below says
              confirming applies the change immediately. A "will NOT happen" heading here
              said the opposite of what the paragraph beneath it states. */}
          <p className="text-xs font-bold text-gray-500 uppercase tracking-wide m-0 mb-1">{t("approval.whatChangesIfConfirm")}</p>
          <p className="text-sm text-gray-500 leading-relaxed m-0">{action.consequence}</p>
        </div>
      </div>

      <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4">
        <p className="text-sm text-yellow-800 m-0 leading-relaxed">
          <span className="font-semibold">{t("approval.prototypeNote.label")}</span> {t("approval.prototypeNote.body")}
        </p>
      </div>

      <div className="flex flex-col gap-3 pt-2">
        <button type="button" onClick={onConfirm} className={`w-full ${BTN_PRIMARY}`}>
          {t("approval.yesProceed")}
        </button>
        <button type="button" onClick={onCancel} className={`w-full ${BTN_SECONDARY}`}>
          {t("approval.notNow")}
        </button>
      </div>
    </div>
  );
}
