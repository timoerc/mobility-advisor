import { useState } from "react";

type PriorityItem = {
  id: string;
  label: string;
  description: string;
  iconSrc: string;
};

const initialPriorityItems: PriorityItem[] = [
  {
    id: "money",
    label: "Money",
    description: "Keep monthly travel costs low.",
    iconSrc: "/assets/piggybank.svg",
  },
  {
    id: "time",
    label: "Time",
    description: "Arrive quickly with fewer delays.",
    iconSrc: "/assets/time.svg",
  },
  {
    id: "sustainability",
    label: "Sustainability",
    description: "Prefer lower-emission mobility options.",
    iconSrc: "/assets/sustainability.svg",
  },
];

function reorderItems(
  items: PriorityItem[],
  draggedId: string,
  targetId: string
) {
  const draggedIndex = items.findIndex((item) => item.id === draggedId);
  const targetIndex = items.findIndex((item) => item.id === targetId);

  if (draggedIndex === -1 || targetIndex === -1) {
    return items;
  }

  const nextItems = [...items];
  const [draggedItem] = nextItems.splice(draggedIndex, 1);
  nextItems.splice(targetIndex, 0, draggedItem);

  return nextItems;
}

export function RankedPrioritiesPage() {
  const [items, setItems] = useState(initialPriorityItems);
  const [draggedId, setDraggedId] = useState<string | null>(null);

  return (
    <div className="page-content">
      <div>
        <h1>Rank your priorities</h1>
        <p className="intro-text">
          Drag the cards into your preferred order. This is only a visual
          alternative for comparing the priority page design.
        </p>
      </div>

      <ol className="ranked-priority-list">
        {items.map((item, index) => (
          <li
            className={
              draggedId === item.id
                ? "ranked-priority-card dragging"
                : "ranked-priority-card"
            }
            draggable
            key={item.id}
            onDragStart={() => setDraggedId(item.id)}
            onDragEnd={() => setDraggedId(null)}
            onDragOver={(event) => event.preventDefault()}
            onDrop={() => {
              if (draggedId) {
                setItems((currentItems) =>
                  reorderItems(currentItems, draggedId, item.id)
                );
              }
            }}
          >
            <span className="rank-badge">
              <img src={item.iconSrc} alt="" />
              <span className="rank-number">{index + 1}</span>
            </span>
            <span className="rank-copy">
              <strong>{item.label}</strong>
              <small>{item.description}</small>
            </span>
            <span className="drag-handle" aria-hidden="true">
              =
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
