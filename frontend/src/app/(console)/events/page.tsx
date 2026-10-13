import { redirect } from "next/navigation";

/** Detections are Edge logs now (type ai.detection); old bookmarks land there. */
export default function EventsPage() {
  redirect("/logs?event_type=ai.detection");
}
