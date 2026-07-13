import { useEffect, useRef, useState } from "react";

type ComboboxProps<T> = {
  items: T[];
  selectedKey: string | null;
  onSelect: (item: T) => void;
  getKey: (item: T) => string;
  getLabel: (item: T) => string;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
};

/**
 * A searchable single-select combobox. Unlike a free-text input, the displayed
 * text always tracks the currently selected item's label — typed text that
 * doesn't exactly match an item is discarded on blur, so it's never possible
 * to leave a value in the field that isn't one of `items`.
 */
export function Combobox<T>({
  items,
  selectedKey,
  onSelect,
  getKey,
  getLabel,
  placeholder,
  disabled,
  className,
}: ComboboxProps<T>) {
  const selected = items.find((i) => getKey(i) === selectedKey) ?? null;
  const selectedLabel = selected ? getLabel(selected) : "";

  const [query, setQuery] = useState(selectedLabel);
  const [open, setOpen] = useState(false);
  const [highlighted, setHighlighted] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setQuery(selectedLabel);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedKey]);

  useEffect(() => {
    function onPointerDown(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setQuery(selectedLabel);
      }
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedLabel]);

  const filtered = items.filter((i) =>
    getLabel(i).toLowerCase().includes(query.toLowerCase()),
  );

  const commit = (item: T) => {
    onSelect(item);
    setQuery(getLabel(item));
    setOpen(false);
  };

  const revertIfUnmatched = () => {
    const exact = items.find((i) => getLabel(i) === query);
    if (!exact) setQuery(selectedLabel);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!open) {
      if (e.key === "ArrowDown" || e.key === "Enter") {
        setOpen(true);
        setHighlighted(0);
        e.preventDefault();
      }
      return;
    }
    if (e.key === "ArrowDown") {
      setHighlighted((h) => Math.min(h + 1, filtered.length - 1));
      e.preventDefault();
    } else if (e.key === "ArrowUp") {
      setHighlighted((h) => Math.max(h - 1, 0));
      e.preventDefault();
    } else if (e.key === "Enter") {
      if (filtered[highlighted]) commit(filtered[highlighted]);
      e.preventDefault();
    } else if (e.key === "Escape") {
      setOpen(false);
      setQuery(selectedLabel);
    }
  };

  return (
    <div ref={containerRef} className="relative">
      <input
        type="text"
        role="combobox"
        aria-expanded={open}
        aria-autocomplete="list"
        value={query}
        disabled={disabled}
        placeholder={placeholder}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
          setHighlighted(0);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={handleKeyDown}
        onBlur={revertIfUnmatched}
        className={className}
      />
      {open && filtered.length > 0 && (
        <ul className="absolute z-10 mt-1 w-full max-h-56 overflow-auto bg-white border border-gray-200 rounded-lg shadow-lg py-1">
          {filtered.map((item, idx) => (
            <li
              key={getKey(item)}
              onMouseDown={(e) => {
                e.preventDefault();
                commit(item);
              }}
              className={`px-3 py-2 text-sm cursor-pointer ${
                idx === highlighted ? "bg-red-50 text-brand-red" : "hover:bg-gray-50"
              }`}
            >
              {getLabel(item)}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
