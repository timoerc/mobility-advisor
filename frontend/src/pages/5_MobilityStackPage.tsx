import { useEffect, useMemo, useRef, useState } from "react";
import { SubscriptionCard } from "../components/SubscriptionCard";
import { fetchCatalog } from "../api";
import type { CatalogOption } from "../api";
import type {
  MobilityMode,
  SubscriptionEntry,
} from "../types";

type MobilityStackPageProps = {
  subscriptions: SubscriptionEntry[];
  onChange: (subscriptions: SubscriptionEntry[]) => void;
  userAge: number | null;
};

const SECTIONS: { mode: MobilityMode; label: string }[] = [
  { mode: "rail", label: "Rail" },
  { mode: "car_share", label: "Carsharing" },
  { mode: "car_rental", label: "Car Rental" },
  { mode: "flight", label: "Flight" },
  { mode: "bus", label: "Bus" },
];

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

const inputClass =
  "border border-gray-300 rounded-lg px-3 py-2 w-full focus:outline-none focus:border-brand-red focus:ring-2 focus:ring-red-100 bg-white text-sm";
const labelClass = "flex flex-col gap-1";
const labelTextClass = "font-semibold text-xs text-gray-600";

function isEligible(opt: CatalogOption, age: number | null): boolean {
  const elig = opt.eligibility;
  if (!elig) return true;
  if (age === null) return true;
  if (elig.min_age !== null && age < elig.min_age) return false;
  if (elig.max_age !== null && age > elig.max_age) return false;
  return true;
}

function SubscriptionForm({
  form,
  onFormChange,
  onSave,
  onCancel,
  saveLabel = "Add",
  catalogOptions,
  userAge,
}: {
  form: FormState;
  onFormChange: (f: FormState) => void;
  onSave: () => void;
  onCancel: () => void;
  saveLabel?: string;
  catalogOptions: CatalogOption[];
  userAge: number | null;
}) {
  const set = (patch: Partial<FormState>) =>
    onFormChange({ ...form, ...patch });

  const modeOptions = useMemo(
    () => catalogOptions.filter((o) => o.mode === form.mode && isEligible(o, userAge)),
    [catalogOptions, form.mode, userAge],
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

  const handleProductChange = (product: string) => {
    const match = modeOptions.find((o) => o.provider === form.provider && o.product === product);
    set({ product, id: match?.id ?? "" });
  };

  return (
    <div className="border border-gray-200 rounded-lg p-4 bg-gray-50 flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3">
        <label className={labelClass}>
          <span className={labelTextClass}>Provider</span>
          {providers.length > 0 ? (
            <select
              value={form.provider ?? ""}
              onChange={(e) => handleProviderChange(e.target.value)}
              className={inputClass}
            >
              <option value="">— select —</option>
              {providers.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          ) : (
            <input
              type="text"
              value={form.provider ?? ""}
              onChange={(e) => set({ provider: e.target.value })}
              placeholder="e.g. Deutsche Bahn"
              className={inputClass}
            />
          )}
        </label>
        <label className={labelClass}>
          <span className={labelTextClass}>Product</span>
          {form.provider && products.length > 0 ? (
            <select
              value={form.product ?? ""}
              onChange={(e) => handleProductChange(e.target.value)}
              className={inputClass}
            >
              <option value="">— select —</option>
              {products.map((o) => (
                <option key={o.id} value={o.product}>{o.product}</option>
              ))}
            </select>
          ) : (
            <input
              type="text"
              value={form.product ?? ""}
              onChange={(e) => set({ product: e.target.value })}
              placeholder="e.g. BahnCard 50"
              className={inputClass}
            />
          )}
        </label>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <label className={labelClass}>
          <span className={labelTextClass}>Valid from</span>
          <input
            type="date"
            value={form.started ?? ""}
            onChange={(e) => set({ started: e.target.value })}
            className={inputClass}
          />
        </label>
        <label className={labelClass}>
          <span className={labelTextClass}>Next renewal / expiry</span>
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
          Cancel
        </button>
        <button
          type="button"
          onClick={onSave}
          disabled={!form.provider || !form.product}
          className="px-4 py-2 text-sm font-semibold bg-brand-red text-white rounded-lg border-0 cursor-pointer hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {saveLabel}
        </button>
      </div>
    </div>
  );
}

function SectionAccordion({
  mode,
  label,
  subscriptions,
  onAdd,
  onRemove,
  onEdit,
  editingEntry,
  onEditDone,
  catalogOptions,
  userAge,
}: {
  mode: MobilityMode;
  label: string;
  subscriptions: SubscriptionEntry[];
  onAdd: (entry: SubscriptionEntry) => void;
  onRemove: (id: string) => void;
  onEdit: (entry: SubscriptionEntry) => void;
  editingEntry: SubscriptionEntry | null;
  onEditDone: (entryToRestore: SubscriptionEntry | null) => void;
  catalogOptions: CatalogOption[];
  userAge: number | null;
}) {
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
          <span className="font-semibold text-sm">{label}</span>
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
              saveLabel={editingId.current ? "Save" : "Add"}
              catalogOptions={catalogOptions}
              userAge={userAge}
            />
          ) : (
            <button
              type="button"
              onClick={() => setAddingForm(emptyForm(mode))}
              className="flex items-center justify-center gap-2 py-3 border-2 border-dashed border-gray-300 rounded-lg text-sm text-gray-500 hover:border-brand-red hover:text-brand-red cursor-pointer bg-transparent w-full transition-colors"
            >
              <span className="text-lg leading-none">+</span> Add service
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
  userAge,
}: MobilityStackPageProps) {
  const [loading, setLoading] = useState(false);
  const [editingEntry, setEditingEntry] = useState<SubscriptionEntry | null>(null);
  const [catalogOptions, setCatalogOptions] = useState<CatalogOption[]>([]);
  const fetchedRef = useRef(false);

  useEffect(() => {
    fetchCatalog().then(setCatalogOptions).catch(console.warn);
  }, []);

  useEffect(() => {
    if (subscriptions.length > 0 || fetchedRef.current) return;
    fetchedRef.current = true;
    setLoading(true);
    fetch("/api/detected-subscriptions.json")
      .then((r) => {
        if (!r.ok) throw new Error(r.statusText);
        return r.json();
      })
      .then((data: SubscriptionEntry[]) => {
        if (Array.isArray(data)) onChange(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
          Current mobility stack
        </h1>
        <p className="text-gray-500 leading-relaxed m-0">
          {loading
            ? "Scanning your connected accounts for active subscriptions…"
            : "We've detected your active subscriptions from your connected accounts. Review, edit, or add more."}
        </p>
      </div>

      <div className="flex flex-col gap-3">
        {SECTIONS.map(({ mode, label }) => (
          <SectionAccordion
            key={mode}
            mode={mode}
            label={label}
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
            userAge={userAge}
          />
        ))}
      </div>

      {!loading && subscriptions.length === 0 && (
        <p className="text-xs text-gray-400 text-center">
          No services detected — skip to continue with an empty stack.
        </p>
      )}
    </div>
  );
}
