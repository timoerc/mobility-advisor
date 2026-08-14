import { useEffect, useMemo, useRef, useState } from "react";
import { SubscriptionCard } from "../components/SubscriptionCard";
import { Combobox } from "../components/Combobox";
import { fetchCatalog } from "../api";
import type { CatalogOption } from "../api";
import { useI18n, formatCurrencyPrecise } from "../i18n";
import type { Language } from "../i18n";
import { MODE_LABEL_KEYS } from "../labels";
import type {
  MobilityMode,
  SubscriptionEntry,
} from "../types";
import { INPUT } from "../ui";

type MobilityStackPageProps = {
  subscriptions: SubscriptionEntry[];
  onChange: (subscriptions: SubscriptionEntry[]) => void;
};

// Reuses the mode.* translation keys (see labels.ts) rather than a separate label set, so the
// wording stays in one place.
const SECTIONS: MobilityMode[] = ["rail", "car_share", "car_rental", "flight", "bus"];

type FormState = Partial<SubscriptionEntry> & {
  mode: MobilityMode;
};

function emptyForm(mode: MobilityMode): FormState {
  return {
    mode,
    id: "",
    provider: "",
    product: "",
    next_renewal_date: "",
    started: "",
  };
}

const inputClass = `${INPUT} text-sm`;
const labelClass = "flex flex-col gap-1";
const labelTextClass = "font-semibold text-xs text-gray-600";

function productLabel(lang: Language, o: CatalogOption): string {
  return `${o.product} — ${formatCurrencyPrecise(lang, o.monthly_cost_eur)}/mo`;
}

function SubscriptionForm({
  form,
  onFormChange,
  onSave,
  onCancel,
  saveLabel,
  catalogOptions,
}: {
  form: FormState;
  onFormChange: (f: FormState) => void;
  onSave: () => void;
  onCancel: () => void;
  // Always passed by the caller (SectionAccordion), which resolves it to a translated
  // "Save"/"Add" — no English-literal default needed here.
  saveLabel: string;
  catalogOptions: CatalogOption[];
}) {
  const { language, t } = useI18n();
  const set = (patch: Partial<FormState>) =>
    onFormChange({ ...form, ...patch });

  // Every mode has at least one catalog option, so this (and `products` once a
  // provider is picked) is never empty — declaring what you already hold isn't
  // gated by today's signup eligibility, so no age filtering here.
  const modeOptions = useMemo(
    () => catalogOptions.filter((o) => o.mode === form.mode),
    [catalogOptions, form.mode],
  );

  const providers = useMemo(
    () => [...new Set(modeOptions.map((o) => o.provider))],
    [modeOptions],
  );

  const products = useMemo(
    () => modeOptions.filter((o) => o.provider === form.provider),
    [modeOptions, form.provider],
  );

  const handleProviderChange = (provider: string) => {
    const matching = modeOptions.filter((o) => o.provider === provider);
    if (matching.length === 1) {
      set({ provider, product: matching[0].product, id: matching[0].id });
    } else {
      set({ provider, product: "", id: "" });
    }
  };

  const handleProductChange = (option: CatalogOption) => {
    set({ product: option.product, id: option.id });
  };

  return (
    <div className="border border-gray-200 rounded-lg p-4 bg-gray-50 flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3">
        <label className={labelClass}>
          <span className={labelTextClass}>{t("onboarding.mobilityStack.provider")}</span>
          <Combobox
            items={providers}
            selectedKey={form.provider || null}
            onSelect={handleProviderChange}
            getKey={(p) => p}
            getLabel={(p) => p}
            placeholder={t("onboarding.mobilityStack.provider.placeholder")}
            className={inputClass}
          />
        </label>
        <label className={labelClass}>
          <span className={labelTextClass}>{t("onboarding.mobilityStack.product")}</span>
          <Combobox
            items={products}
            selectedKey={form.id || null}
            onSelect={handleProductChange}
            getKey={(o) => o.id}
            getLabel={(o) => productLabel(language, o)}
            placeholder={form.provider ? t("onboarding.mobilityStack.product.placeholder") : t("onboarding.mobilityStack.product.selectProviderFirst")}
            disabled={!form.provider}
            className={inputClass}
          />
        </label>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <label className={labelClass}>
          <span className={labelTextClass}>{t("onboarding.mobilityStack.validFrom")}</span>
          <input
            type="date"
            value={form.started ?? ""}
            onChange={(e) => set({ started: e.target.value })}
            className={inputClass}
          />
        </label>
        <label className={labelClass}>
          <span className={labelTextClass}>{t("onboarding.mobilityStack.nextRenewal")}</span>
          <input
            type="date"
            value={form.next_renewal_date ?? ""}
            onChange={(e) => set({ next_renewal_date: e.target.value })}
            className={inputClass}
          />
        </label>
      </div>

      <div className="flex gap-2 justify-end">
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 text-sm text-gray-500 hover:text-gray-700 bg-transparent border-0 cursor-pointer"
        >
          {t("common.cancel")}
        </button>
        <button
          type="button"
          onClick={onSave}
          disabled={!form.provider || !form.product || !form.started || !form.next_renewal_date}
          className="px-4 py-2 text-sm font-semibold bg-brand-red text-white rounded-lg border-0 cursor-pointer hover:bg-brand-red-hover active:bg-brand-red-deep disabled:opacity-40 disabled:cursor-not-allowed transition-colors duration-150"
        >
          {saveLabel}
        </button>
      </div>
    </div>
  );
}

function SectionAccordion({
  mode,
  subscriptions,
  onAdd,
  onRemove,
  onEdit,
  editingEntry,
  onEditDone,
  catalogOptions,
}: {
  mode: MobilityMode;
  subscriptions: SubscriptionEntry[];
  onAdd: (entry: SubscriptionEntry) => void;
  onRemove: (id: string) => void;
  onEdit: (entry: SubscriptionEntry) => void;
  editingEntry: SubscriptionEntry | null;
  onEditDone: (entryToRestore: SubscriptionEntry | null) => void;
  catalogOptions: CatalogOption[];
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [addingForm, setAddingForm] = useState<FormState | null>(null);
  const editingId = useRef<string | null>(null);

  useEffect(() => {
    if (!editingEntry) return;
    editingId.current = editingEntry.id;
    setOpen(true);
    setAddingForm({ ...editingEntry });
  }, [editingEntry]);

  const sectionEntries = subscriptions.filter((s) => s.mode === mode);

  const handleSave = () => {
    if (!addingForm) return;
    const entry: SubscriptionEntry = {
      id: addingForm.id || editingId.current || crypto.randomUUID(),
      mode,
      provider: addingForm.provider ?? "",
      product: addingForm.product ?? "",
      next_renewal_date: addingForm.next_renewal_date ?? "",
      started: addingForm.started ?? "",
    };
    onAdd(entry);
    setAddingForm(null);
    if (editingId.current) {
      editingId.current = null;
      onEditDone(null);
    }
  };

  const handleCancel = () => {
    const wasEditing = !!editingId.current;
    const toRestore = wasEditing ? editingEntry : null;
    setAddingForm(null);
    if (wasEditing) {
      editingId.current = null;
      onEditDone(toRestore);
    }
  };

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-3 bg-white hover:bg-gray-50 cursor-pointer border-0 text-left"
      >
        <div className="flex items-center gap-3">
          <span className="font-semibold text-sm">{t(MODE_LABEL_KEYS[mode])}</span>
          {sectionEntries.length > 0 && (
            <span className="text-xs bg-brand-red text-white rounded-full px-2 py-0.5 font-semibold">
              {sectionEntries.length}
            </span>
          )}
        </div>
        <span className="text-gray-400 text-lg leading-none">
          {open ? "−" : "+"}
        </span>
      </button>

      {open && (
        <div className="border-t border-gray-100 p-4 flex flex-col gap-3 bg-white">
          {sectionEntries.map((entry) => (
            <SubscriptionCard
              key={entry.id}
              entry={entry}
              onRemove={onRemove}
              onEdit={onEdit}
            />
          ))}

          {addingForm ? (
            <SubscriptionForm
              form={addingForm}
              onFormChange={setAddingForm}
              onSave={handleSave}
              onCancel={handleCancel}
              saveLabel={editingId.current ? t("common.save") : t("onboarding.mobilityStack.add")}
              catalogOptions={catalogOptions}
            />
          ) : (
            <button
              type="button"
              onClick={() => setAddingForm(emptyForm(mode))}
              className="flex items-center justify-center gap-2 py-3 border-2 border-dashed border-gray-300 rounded-lg text-sm text-gray-500 hover:border-brand-red hover:text-brand-red cursor-pointer bg-transparent w-full transition-colors"
            >
              <span className="text-lg leading-none">+</span> {t("onboarding.mobilityStack.addService")}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export function MobilityStackPage({
  subscriptions,
  onChange,
}: MobilityStackPageProps) {
  const { t } = useI18n();
  const [loading, setLoading] = useState(false);
  const [editingEntry, setEditingEntry] = useState<SubscriptionEntry | null>(null);
  const [catalogOptions, setCatalogOptions] = useState<CatalogOption[]>([]);
  const fetchedRef = useRef(false);

  useEffect(() => {
    fetchCatalog().then(setCatalogOptions).catch(console.warn);
  }, []);

  useEffect(() => {
    if (subscriptions.length > 0 || fetchedRef.current) return;
    if (catalogOptions.length === 0) return; // wait until we can resolve ids against the catalog
    fetchedRef.current = true;
    setLoading(true);
    fetch("/api/detected-subscriptions.json")
      .then((r) => {
        if (!r.ok) throw new Error(r.statusText);
        return r.json();
      })
      .then((data: { id: string; started?: string; next_renewal_date?: string }[]) => {
        const byId = new Map(catalogOptions.map((o) => [o.id, o]));
        const resolved: SubscriptionEntry[] = data.flatMap((d) => {
          const match = byId.get(d.id);
          if (!match) return [];
          return [
            {
              id: match.id,
              mode: match.mode as MobilityMode,
              provider: match.provider,
              product: match.product,
              started: d.started ?? "",
              next_renewal_date: d.next_renewal_date ?? "",
              detected: true,
            },
          ];
        });
        if (resolved.length) onChange(resolved);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [catalogOptions]);

  const add = (entry: SubscriptionEntry) =>
    onChange([...subscriptions, entry]);

  const remove = (id: string) =>
    onChange(subscriptions.filter((s) => s.id !== id));

  const handleEdit = (entry: SubscriptionEntry) => {
    remove(entry.id);
    setEditingEntry(entry);
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-bold leading-tight mb-2">
          {t("onboarding.mobilityStack.heading")}
        </h1>
        <p className="text-gray-500 leading-relaxed m-0">
          {loading
            ? t("onboarding.mobilityStack.scanning")
            : t("onboarding.mobilityStack.detected")}
        </p>
      </div>

      <div className="flex flex-col gap-3">
        {SECTIONS.map((mode) => (
          <SectionAccordion
            key={mode}
            mode={mode}
            subscriptions={subscriptions}
            onAdd={add}
            onRemove={remove}
            onEdit={handleEdit}
            editingEntry={editingEntry?.mode === mode ? editingEntry : null}
            onEditDone={(entryToRestore) => {
              if (entryToRestore) onChange([...subscriptions, entryToRestore]);
              setEditingEntry(null);
            }}
            catalogOptions={catalogOptions}
          />
        ))}
      </div>

      {!loading && subscriptions.length === 0 && (
        <p className="text-xs text-gray-400 text-center">
          {t("onboarding.mobilityStack.noneDetected")}
        </p>
      )}
    </div>
  );
}
