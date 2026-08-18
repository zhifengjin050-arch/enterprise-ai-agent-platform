import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "-"
  try {
    return new Date(dateStr).toLocaleString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    })
  } catch {
    return dateStr
  }
}

export function formatNumber(n: number | null | undefined): string {
  if (n === null || n === undefined) return "-"
  return n.toLocaleString("zh-CN")
}

export function formatCost(cost: number | null | undefined): string {
  if (cost === null || cost === undefined) return "-"
  return `$${cost.toFixed(4)}`
}