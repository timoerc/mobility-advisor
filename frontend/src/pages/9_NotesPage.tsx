type NotesPageProps = {
  notes: string;
  onChange: (notes: string) => void;
};

export function NotesPage({ notes, onChange }: NotesPageProps) {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-bold leading-tight mb-2">
          Anything else?
        </h1>
        <p className="text-gray-500 leading-relaxed m-0">
          Add optional details such as comfort needs, accessibility, luggage,
          or preferred travel times.
        </p>
      </div>

      <label className="flex flex-col gap-2">
        <span className="font-semibold text-sm text-gray-700">Notes</span>
        <textarea
          value={notes}
          onChange={(event) => onChange(event.target.value)}
          placeholder="For example: I prefer direct trains and need space for luggage."
          className="border border-gray-300 rounded-lg px-4 py-3 min-h-[180px] resize-y w-full focus:outline-none focus:border-brand-red focus:ring-2 focus:ring-red-100 transition-[border-color,box-shadow] duration-150"
        />
      </label>
    </div>
  );
}
