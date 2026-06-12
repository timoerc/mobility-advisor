import { useRef } from "react";
import type { OnboardingPreferences } from "../types";

type Priorities = OnboardingPreferences["priorities"];

type Point = {
  x: number;
  y: number;
};

type PriorityTriangleProps = {
  priorities: Priorities;
  onChange: (priorities: Priorities) => void;
};

const moneyPoint: Point = { x: 59, y: 223 };
const timePoint: Point = { x: 241, y: 223 };
const sustainabilityPoint: Point = { x: 150, y: 64 };

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function closestPointOnLine(point: Point, start: Point, end: Point): Point {
  const lineX = end.x - start.x;
  const lineY = end.y - start.y;
  const lengthSquared = lineX * lineX + lineY * lineY;
  const amount =
    ((point.x - start.x) * lineX + (point.y - start.y) * lineY) /
    lengthSquared;
  const clampedAmount = clamp(amount, 0, 1);

  return {
    x: start.x + clampedAmount * lineX,
    y: start.y + clampedAmount * lineY,
  };
}

function distanceSquared(first: Point, second: Point) {
  return (first.x - second.x) ** 2 + (first.y - second.y) ** 2;
}

function getBarycentricWeights(point: Point): Priorities {
  const denominator =
    (timePoint.y - sustainabilityPoint.y) *
      (moneyPoint.x - sustainabilityPoint.x) +
    (sustainabilityPoint.x - timePoint.x) *
      (moneyPoint.y - sustainabilityPoint.y);

  const money =
    ((timePoint.y - sustainabilityPoint.y) *
      (point.x - sustainabilityPoint.x) +
      (sustainabilityPoint.x - timePoint.x) *
        (point.y - sustainabilityPoint.y)) /
    denominator;

  const time =
    ((sustainabilityPoint.y - moneyPoint.y) *
      (point.x - sustainabilityPoint.x) +
      (moneyPoint.x - sustainabilityPoint.x) *
        (point.y - sustainabilityPoint.y)) /
    denominator;

  const sustainability = 1 - money - time;

  return {
    money,
    time,
    sustainability,
  };
}

function pointFromPriorities(priorities: Priorities): Point {
  return {
    x:
      priorities.money * moneyPoint.x +
      priorities.time * timePoint.x +
      priorities.sustainability * sustainabilityPoint.x,
    y:
      priorities.money * moneyPoint.y +
      priorities.time * timePoint.y +
      priorities.sustainability * sustainabilityPoint.y,
  };
}

function pointIsInsideTriangle(point: Point) {
  const weights = getBarycentricWeights(point);

  return (
    weights.money >= 0 &&
    weights.time >= 0 &&
    weights.sustainability >= 0 &&
    weights.money <= 1 &&
    weights.time <= 1 &&
    weights.sustainability <= 1
  );
}

function closestPointInTriangle(point: Point): Point {
  if (pointIsInsideTriangle(point)) {
    return point;
  }

  const candidates = [
    closestPointOnLine(point, moneyPoint, timePoint),
    closestPointOnLine(point, timePoint, sustainabilityPoint),
    closestPointOnLine(point, sustainabilityPoint, moneyPoint),
  ];

  return candidates.reduce((closest, candidate) =>
    distanceSquared(point, candidate) < distanceSquared(point, closest)
      ? candidate
      : closest
  );
}

function roundPriorities(priorities: Priorities): Priorities {
  return {
    money: Number(priorities.money.toFixed(3)),
    time: Number(priorities.time.toFixed(3)),
    sustainability: Number(priorities.sustainability.toFixed(3)),
  };
}

export function PriorityTriangle({
  priorities,
  onChange,
}: PriorityTriangleProps) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const dotPoint = pointFromPriorities(priorities);

  const updateFromPointer = (clientX: number, clientY: number) => {
    const svg = svgRef.current;

    if (!svg) {
      return;
    }

    const rect = svg.getBoundingClientRect();
    const rawPoint = {
      x: ((clientX - rect.left) / rect.width) * 300,
      y: ((clientY - rect.top) / rect.height) * 280,
    };
    const trianglePoint = closestPointInTriangle(rawPoint);

    onChange(roundPriorities(getBarycentricWeights(trianglePoint)));
  };

  return (
    <div className="priority-triangle">
      <svg
        ref={svgRef}
        viewBox="0 0 300 280"
        role="img"
        aria-label="Priority triangle with draggable preference dot"
        onPointerDown={(event) => {
          event.currentTarget.setPointerCapture(event.pointerId);
          updateFromPointer(event.clientX, event.clientY);
        }}
        onPointerMove={(event) => {
          if (event.buttons === 1) {
            updateFromPointer(event.clientX, event.clientY);
          }
        }}
      >
        <polygon
          className="priority-triangle-area"
          points={`${moneyPoint.x},${moneyPoint.y} ${timePoint.x},${timePoint.y} ${sustainabilityPoint.x},${sustainabilityPoint.y}`}
        />
        <image
          className="priority-label-icon"
          href="/assets/piggybank.svg"
          x={moneyPoint.x - 12}
          y={moneyPoint.y + 8}
        />
        <text x={moneyPoint.x} y={moneyPoint.y + 44} textAnchor="middle">
          Money
        </text>
        <image
          className="priority-label-icon"
          href="/assets/time.svg"
          x={timePoint.x - 12}
          y={timePoint.y + 8}
        />
        <text x={timePoint.x} y={timePoint.y + 44} textAnchor="middle">
          Time
        </text>
        <image
          className="priority-label-icon"
          href="/assets/sustainability.svg"
          x={sustainabilityPoint.x - 12}
          y={sustainabilityPoint.y - 46}
        />
        <text
          x={sustainabilityPoint.x}
          y={sustainabilityPoint.y - 14}
          textAnchor="middle"
        >
          Sustainability
        </text>
        <circle className="priority-corner" cx={moneyPoint.x} cy={moneyPoint.y} />
        <circle className="priority-corner" cx={timePoint.x} cy={timePoint.y} />
        <circle
          className="priority-corner"
          cx={sustainabilityPoint.x}
          cy={sustainabilityPoint.y}
        />
        <circle className="priority-dot" cx={dotPoint.x} cy={dotPoint.y} />
      </svg>
    </div>
  );
}
