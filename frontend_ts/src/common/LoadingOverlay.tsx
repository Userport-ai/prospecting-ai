import React from "react";

const LoadingOverlay: React.FC<{ loading: boolean }> = ({ loading }) => {
  return loading ? (
    <div className="fixed inset-0 flex items-center justify-center bg-black bg-opacity-50 z-50">
      <div className="flex flex-col items-center w-[10rem] p-6 bg-white rounded-lg shadow-lg">
        <p className="text-lg font-semibold">Loading...</p>
        <div className="mt-4 w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    </div>
  ) : null;
};

export default LoadingOverlay;
