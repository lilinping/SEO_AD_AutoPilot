import { getOverview } from "@/lib/api";
import { HomeContent } from "@/components/HomeContent";
import { fallbackDashboard } from "@/lib/fallback";

export default async function HomePage() {
  let overview = fallbackDashboard;
  
  try {
    overview = await getOverview();
  } catch (error) {
    console.error("Failed to fetch overview:", error);
  }

  return <HomeContent overview={overview} />;
}
