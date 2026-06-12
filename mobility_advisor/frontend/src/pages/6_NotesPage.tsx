type NotesPageProps = {
  notes: string;
  onChange: (notes: string) => void;
};

export function NotesPage({ notes, onChange }: NotesPageProps) {
  return (
    <div className="page-content">
      <div>
        <h1>Anything else?</h1>
        <p className="intro-text">
          Add optional details such as comfort needs, accessibility, luggage, or
          preferred travel times.
        </p>
      </div>

      <label className="notes-field">
        <span className="field-title">Notes</span>
        <textarea
          value={notes}
          onChange={(event) => onChange(event.target.value)}
          placeholder="For example: I prefer direct trains and need space for luggage."
        />
      </label>
    </div>
  );
}
