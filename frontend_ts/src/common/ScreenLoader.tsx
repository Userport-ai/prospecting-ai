import { cn } from "@/lib/utils"; // Replace with your utilities if you have a custom `cn` function.

export const ScreenLoader = () => {
  return (
    <div
      className={cn(
        "flex items-center justify-center bg-gray-50 dark:bg-gray-900"
      )}
    >
      <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-purple-500 border-opacity-50"></div>
    </div>
  );
};

export default ScreenLoader;
