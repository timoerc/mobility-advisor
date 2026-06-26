import { useEffect, useRef, useState } from "react";
import { SubscriptionCard } from "../components/SubscriptionCard";
import type {
  CostStructure,
  SubscriptionCategory,
  SubscriptionEntry,
} from "../types";

type MobilityStackPageProps = {
  subscriptions: SubscriptionEntry[];
  onChange: (subscriptions: SubscriptionEntry[]) => void;
};

const SECTIONS: { category: SubscriptionCategory; label: string }[] = [
  { category: "rail_subscription", label: "Rail" },
  { category: "carsharing", label: "Carsharing" },
  { category: "micromobility_ridehailing", label: "Micromobility / Ride-hailing" },
];

const COST_STRUCTURE_LABELS: Record<CostStructure, string> = {
  fixed_recurring: "Fixed recurring (monthly / yearly flat fee)",
  fixed_annual_discount: "Annual discount card (e.g. BahnCard)",
  usage_membership: "Usage membership (e.g. carsharing)",
  pay_per_use: "Pay per use (occasional)",
};

type FormState = Partial<SubscriptionEntry> & {
  cost_structure: CostStructure;
  category: SubscriptionCategory;
};

function emptyForm(category: SubscriptionCategory): FormState {
  return {
    category,
    cost_structure: "fixed_recurring",
    provider: "",
    product: "",
    monthly_cost_eur: 0,
    billing_cycle: "monthly",
    next_renewal_date: "",
    started: "",
    coverage_scope: "",
    notes: "",
  };
}

function computeMonthlyCost(form: FormState): number {
  if (form.cost_structure === "fixed_annual_discount") {
    return form.annual_price ? form.annual_price / 12 : 0;
  }
  if (form.cost_structure === "usage_membership") {
    return form.monthly_fee ?? 0;
  }
  return form.monthly_cost_eur ?? 0;
}

const inputClass =
  "border border-gray-300 rounded-lg px-3 py-2 w-full focus:outline-none focus:border-brand-red focus:ring-2 focus:ring-red-100 bg-white text-sm";
const labelClass = "flex flex-col gap-1";
const labelTextClass = "font-semibold text-xs text-gray-600";

function SubscriptionForm({
  form,
  onFormChange,
  onSave,
  onCancel,
  saveLabel = "Add",
}: {
  form: FormState;
  onFormChange: (f: FormState) => void;
  onSave: () => void;
  onCancel: () => void;
  saveLabel?: string;
}) {
  const set = (patch: Partial<FormState>) =>
    onFormChange({ ...form, ...patch });

  return (
    <div className="border border-gray-200 rounded-lg p-4 bg-gray-50 flex flex-col gap-4">
      <label className={labelClass}>
        <span className={labelTextClass}>Cost structure</span>
        <select
          value={form.cost_structure}
          onChange={(e) =>
            set({ cost_structure: e.target.value as CostStructure })
          }
          className={inputClass}
        >
          {(Object.keys(COST_STRUCTURE_LABELS) as CostStructure[]).map((k) => (
            <option key={k} value={k}>
              {COST_STRUCTURE_LABELS[k]}
            </option>
          ))}
        </select>
      </label>

      <div className="grid grid-cols-2 gap-3">
        <label className={labelClass}>
          <span className={labelTextClass}>Provider</span>
          <input
            type="text"
            value={form.provider ?? ""}
            onChange={(e) => set({ provider: e.target.value })}
            placeholder="e.g. Deutsche Bahn"
            className={inputClass}
          />
        </label>
        <label className={labelClass}>
          <span className={labelTextClass}>Product</span>
          <input
            type="text"
            value={form.product ?? ""}
            onChange={(e) => set({ product: e.target.value })}
            placeholder="e.g. BahnCard 50"
            className={inputClass}
          />
        </label>
      </div>

      {/* fixed_recurring fields */}
      {form.cost_structure === "fixed_recurring" && (
        <>
          <div className="grid grid-cols-2 gap-3">
            <label className={labelClass}>
              <span className={labelTextClass}>Monthly cost (€)</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={form.monthly_cost_eur ?? ""}
                onChange={(e) =>
                  set({ monthly_cost_eur: Number(e.target.value) })
                }
                className={inputClass}
              />
            </label>
            <label className={labelClass}>
              <span className={labelTextClass}>Billing cycle</span>
              <select
                value={form.billing_cycle ?? "monthly"}
                onChange={(e) => set({ billing_cycle: e.target.value })}
                className={inputClass}
              >
                <option value="monthly">Monthly</option>
                <option value="annual">Annual</option>
              </select>
            </label>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <label className={labelClass}>
              <span className={labelTextClass}>Next renewal</span>
              <input
                type="date"
                value={form.next_renewal_date ?? ""}
                onChange={(e) => set({ next_renewal_date: e.target.value })}
                className={inputClass}
              />
            </label>
            <label className={labelClass}>
              <span className={labelTextClass}>Coverage scope</span>
              <input
                type="text"
                value={form.coverage_scope ?? ""}
                onChange={(e) => set({ coverage_scope: e.target.value })}
                placeholder="e.g. Frankfurt VRN"
                className={inputClass}
              />
            </label>
          </div>
        </>
      )}

      {/* fixed_annual_discount fields */}
      {form.cost_structure === "fixed_annual_discount" && (
        <>
          <div className="grid grid-cols-2 gap-3">
            <label className={labelClass}>
              <span className={labelTextClass}>Annual price (€)</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={form.annual_price ?? ""}
                onChange={(e) =>
                  set({ annual_price: Number(e.target.value) })
                }
                className={inputClass}
              />
            </label>
            <label className={labelClass}>
              <span className={labelTextClass}>Discount rate (%)</span>
              <input
                type="number"
                min="0"
                max="100"
                value={form.discount_rate ?? ""}
                onChange={(e) =>
                  set({ discount_rate: Number(e.target.value) })
                }
                placeholder="e.g. 50"
                className={inputClass}
              />
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
              <span className={labelTextClass}>Valid until</span>
              <input
                type="date"
                value={form.next_renewal_date ?? ""}
                onChange={(e) => set({ next_renewal_date: e.target.value })}
                className={inputClass}
              />
            </label>
          </div>
          <label className={labelClass}>
            <span className={labelTextClass}>Travel class</span>
            <select
              value={form.travel_class ?? ""}
              onChange={(e) => set({ travel_class: e.target.value })}
              className={inputClass}
            >
              <option value="">— select —</option>
              <option value="1st">1st class</option>
              <option value="2nd">2nd class</option>
            </select>
          </label>
          {form.annual_price ? (
            <p className="text-xs text-gray-500 m-0">
              ≈ {(form.annual_price / 12).toFixed(2)} €/month
            </p>
          ) : null}
        </>
      )}

      {/* usage_membership fields */}
      {form.cost_structure === "usage_membership" && (
        <>
          <div className="grid grid-cols-2 gap-3">
            <label className={labelClass}>
              <span className={labelTextClass}>Monthly fee (€)</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={form.monthly_fee ?? ""}
                onChange={(e) =>
                  set({ monthly_fee: Number(e.target.value) })
                }
                className={inputClass}
              />
            </label>
            <label className={labelClass}>
              <span className={labelTextClass}>Registration fee (€)</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={form.registration_fee ?? ""}
                onChange={(e) =>
                  set({ registration_fee: Number(e.target.value) })
                }
                className={inputClass}
              />
            </label>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <label className={labelClass}>
              <span className={labelTextClass}>Per-minute rate (€)</span>
              <input
                type="number"
                min="0"
                step="0.001"
                value={form.per_minute_rate ?? ""}
                onChange={(e) =>
                  set({ per_minute_rate: Number(e.target.value) })
                }
                placeholder="e.g. 0.19"
                className={inputClass}
              />
            </label>
            <label className={labelClass}>
              <span className={labelTextClass}>Per-km rate (€)</span>
              <input
                type="number"
                min="0"
                step="0.001"
                value={form.per_km_rate ?? ""}
                onChange={(e) =>
                  set({ per_km_rate: Number(e.target.value) })
                }
                placeholder="e.g. 0.25"
                className={inputClass}
              />
            </label>
          </div>
        </>
      )}

      {/* pay_per_use fields */}
      {form.cost_structure === "pay_per_use" && (
        <>
          <label className={labelClass}>
            <span className={labelTextClass}>Usage frequency</span>
            <select
              value={form.usage_frequency ?? ""}
              onChange={(e) =>
                set({
                  usage_frequency: e.target.value as
                    | "rarely"
                    | "monthly"
                    | "weekly",
                })
              }
              className={inputClass}
            >
              <option value="">— select —</option>
              <option value="rarely">Rarely (a few times a year)</option>
              <option value="monthly">Monthly</option>
              <option value="weekly">Weekly</option>
            </select>
          </label>
          <label className={labelClass}>
            <span className={labelTextClass}>
              Estimated monthly cost (€)
            </span>
            <input
              type="number"
              min="0"
              step="0.01"
              value={form.monthly_cost_eur ?? ""}
              onChange={(e) =>
                set({ monthly_cost_eur: Number(e.target.value) })
              }
              placeholder="Your estimate"
              className={inputClass}
            />
          </label>
        </>
      )}

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
  category,
  label,
  subscriptions,
  onAdd,
  onRemove,
  onEdit,
  editingEntry,
  onEditDone,
}: {
  category: SubscriptionCategory;
  label: string;
  subscriptions: SubscriptionEntry[];
  onAdd: (entry: SubscriptionEntry) => void;
  onRemove: (id: string) => void;
  onEdit: (entry: SubscriptionEntry) => void;
  editingEntry: SubscriptionEntry | null;
  onEditDone: (entryToRestore: SubscriptionEntry | null) => void;
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

  const sectionEntries = subscriptions.filter((s) => s.category === category);

  const handleSave = () => {
    if (!addingForm) return;
    const entry: SubscriptionEntry = {
      id: editingId.current ?? crypto.randomUUID(),
      category,
      cost_structure: addingForm.cost_structure,
      provider: addingForm.provider ?? "",
      product: addingForm.product ?? "",
      monthly_cost_eur: computeMonthlyCost(addingForm),
      billing_cycle: addingForm.billing_cycle ?? "monthly",
      next_renewal_date: addingForm.next_renewal_date ?? "",
      started: addingForm.started ?? "",
      coverage_scope: addingForm.coverage_scope ?? "",
      notes: addingForm.notes ?? "",
      ...(addingForm.cost_structure === "fixed_annual_discount" && {
        annual_price: addingForm.annual_price,
        discount_rate: addingForm.discount_rate,
        travel_class: addingForm.travel_class,
      }),
      ...(addingForm.cost_structure === "usage_membership" && {
        registration_fee: addingForm.registration_fee,
        monthly_fee: addingForm.monthly_fee,
        per_minute_rate: addingForm.per_minute_rate,
        per_km_rate: addingForm.per_km_rate,
      }),
      ...(addingForm.cost_structure === "pay_per_use" && {
        usage_frequency: addingForm.usage_frequency,
      }),
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
            />
          ) : (
            <button
              type="button"
              onClick={() => setAddingForm(emptyForm(category))}
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
}: MobilityStackPageProps) {
  const [loading, setLoading] = useState(false);
  const [editingEntry, setEditingEntry] = useState<SubscriptionEntry | null>(null);
  const fetchedRef = useRef(false);

  useEffect(() => {
    if (subscriptions.length > 0 || fetchedRef.current) return;
    fetchedRef.current = true;
    setLoading(true);
    fetch("/api/detected-subscriptions.json")
      .then((r) => r.json())
      .then((data: SubscriptionEntry[]) => {
        onChange(data);
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
        {SECTIONS.map(({ category, label }) => (
          <SectionAccordion
            key={category}
            category={category}
            label={label}
            subscriptions={subscriptions}
            onAdd={add}
            onRemove={remove}
            onEdit={handleEdit}
            editingEntry={editingEntry?.category === category ? editingEntry : null}
            onEditDone={(entryToRestore) => {
              if (entryToRestore) onChange([...subscriptions, entryToRestore]);
              setEditingEntry(null);
            }}
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
