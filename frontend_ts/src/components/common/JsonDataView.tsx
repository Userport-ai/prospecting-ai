import React, { useState } from "react";
import { ChevronRight, ChevronDown } from "lucide-react";

interface JsonDataViewProps {
    data: object;
    initialExpanded?: boolean;
}

const JsonDataView: React.FC<JsonDataViewProps> = ({
                                                       data,
                                                       initialExpanded = false
                                                   }) => {
    const [isExpanded, setIsExpanded] = useState(initialExpanded);

    const toggleExpand = () => {
        setIsExpanded(!isExpanded);
    };

    // Convert the JSON to a formatted string with indentation
    const formattedJson = JSON.stringify(data, null, 2);

    return (
        <div className="font-mono text-xs">
        <div
            className="flex items-center cursor-pointer text-blue-600 hover:text-blue-800"
    onClick={toggleExpand}
        >
        {isExpanded ? (
                <ChevronDown className="h-4 w-4 mr-1" />
            ) : (
                <ChevronRight className="h-4 w-4 mr-1" />
            )}
        <span>{isExpanded ? "Hide JSON Data" : "View JSON Data"}</span>
        </div>

    {isExpanded && (
        <pre className="mt-2 p-2 bg-gray-50 border border-gray-200 rounded overflow-x-auto max-h-64">
            {formattedJson}
            </pre>
    )}
    </div>
);
};

export default JsonDataView;