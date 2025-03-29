// src/components/custom-columns/CreateCustomColumnDialog.tsx
import React, { useState } from 'react';
import { DialogProps } from "@radix-ui/react-dialog";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
    Dialog, DialogContent, DialogHeader, DialogFooter, DialogTitle, DialogDescription
} from "@/components/ui/dialog";
import {
    Form, FormControl, FormDescription, FormField, FormItem, FormLabel, FormMessage
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox"; // For Is Active & Context Types
import { Product } from '@/services/Products'; // Adjust path
import { CreateCustomColumnRequest, createCustomColumn, CustomColumn } from '@/services/CustomColumn';
import { useAuthContext } from '@/auth/AuthProvider'; // Adjust path
import ResponseConfigInput from './ResponseConfigInput';
import ScreenLoader from '@/common/ScreenLoader'; // Adjust path

// --- Zod Schema ---
// Making response_config optional initially and refining based on response_type
const baseSchema = z.object({
    product: z.string().uuid("Please select a valid product."),
    name: z.string().min(1, "Column Name is required."),
    description: z.string().optional(),
    question: z.string().min(1, "Question/Prompt is required."),
    entity_type: z.enum(["account", "lead"]),
    response_type: z.enum(["string", "json_object", "boolean", "number", "enum"]),
    response_config: z.object({
        allowed_values: z.array(z.string().min(1, "Enum value cannot be empty.")).optional()
        // Add other response_config fields here if needed
    }).optional(),
    ai_config: z.object({
        model: z.string().min(1, "AI Model is required."),
        temperature: z.coerce.number().min(0).max(1), // Coerce to number, validate range
        use_internet: z.boolean().optional()
    }),
    context_type: z.array(z.string()).min(1, "At least one Context Type is required."),
    refresh_interval: z.coerce.number().int().positive().optional().nullable(), // Optional integer > 0
    is_active: z.boolean().optional(),
});

// Refine schema for enum response_type
const refinedSchema = baseSchema.refine(data => {
    if (data.response_type === 'enum') {
        return data.response_config?.allowed_values && data.response_config.allowed_values.length >= 1;
    }
    return true;
}, {
    message: "Allowed Values are required for Enum type and must contain at least one value.",
    path: ["response_config.allowed_values"], // Point error to the correct field
});

// --- Component Props ---
interface CreateCustomColumnDialogProps extends DialogProps {
    products: Product[];
    onSuccess: (newColumn: CustomColumn) => void; // Callback on successful creation
}

// --- Available Context Types (Adjust based on your actual backend options) ---
const AVAILABLE_CONTEXT_TYPES = [
    { id: 'company_profile', label: 'Company Profile' },
    { id: 'lead_activity', label: 'Lead Activity' },
    { id: 'recent_news', label: 'Recent News' },
    { id: 'website_data', label: 'Website Data' },
];

// --- Available AI Models (Adjust as needed) ---
const AVAILABLE_AI_MODELS = ["gemini-pro", "gpt-4", "claude-3"];


// --- The Component ---
const CreateCustomColumnDialog: React.FC<CreateCustomColumnDialogProps> = ({
                                                                               products,
                                                                               open,
                                                                               onOpenChange,
                                                                               onSuccess
                                                                           }) => {
    const authContext = useAuthContext();
    const [loading, setLoading] = useState(false);
    const [apiError, setApiError] = useState<string | null>(null);

    const form = useForm<CreateCustomColumnRequest>({
        resolver: zodResolver(refinedSchema),
        defaultValues: {
            name: "",
            description: "",
            question: "",
            entity_type: "account",
            response_type: "string",
            response_config: { allowed_values: [] },
            ai_config: { model: AVAILABLE_AI_MODELS[0], temperature: 0.1 },
            context_type: [AVAILABLE_CONTEXT_TYPES[0].id], // Default context
            refresh_interval: 24 * 7, // Default to weekly
            is_active: true,
            product: products.length > 0 ? products[0].id : '', // Default to first product or empty
        },
    });

    // Reset form when dialog closes
    React.useEffect(() => {
        if (!open) {
            form.reset();
            setApiError(null);
        }
    }, [open, form]);

    const onSubmit = async (data: CreateCustomColumnRequest) => {
        setLoading(true);
        setApiError(null);
        console.log("Submitting data:", data); // Debug log

        try {
            const newColumn = await createCustomColumn(authContext, data);
            onSuccess(newColumn); // Call success callback
            if (onOpenChange) onOpenChange(false); // Close dialog on success
        } catch (error: any) {
            console.error("Failed to create custom column:", error);
            setApiError(error.message || "An unexpected error occurred.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>Create New Custom Column</DialogTitle>
                    <DialogDescription>
                        Define a new column powered by AI insights based on your prompt.
                    </DialogDescription>
                </DialogHeader>

                {apiError && <p className="text-sm text-red-600 bg-red-50 p-2 rounded border border-red-200">{apiError}</p>}

                <Form {...form}>
                    <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
                        {/* Product Selection */}
                        <FormField
                            control={form.control}
                            name="product"
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel>Product *</FormLabel>
                                    <Select onValueChange={field.onChange} defaultValue={field.value}>
                                        <FormControl>
                                            <SelectTrigger>
                                                <SelectValue placeholder="Select Product..." />
                                            </SelectTrigger>
                                        </FormControl>
                                        <SelectContent>
                                            {products.map(p => (
                                                <SelectItem key={p.id} value={p.id!}>{p.name}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                    <FormDescription>
                                        Associate this column with a specific product playbook.
                                    </FormDescription>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />

                        {/* Column Name */}
                        <FormField control={form.control} name="name" render={({ field }) => ( <FormItem> <FormLabel>Column Name *</FormLabel><FormControl><Input placeholder="e.g., Fit Score" {...field} /></FormControl><FormDescription>The name displayed in the table header.</FormDescription><FormMessage /></FormItem>)} />
                        {/* Description */}
                        <FormField control={form.control} name="description" render={({ field }) => ( <FormItem> <FormLabel>Description</FormLabel><FormControl><Textarea placeholder="e.g., How well this account fits our target profile" {...field} value={field.value || ''} /></FormControl><FormMessage /></FormItem>)} />
                        {/* Question */}
                        <FormField control={form.control} name="question" render={({ field }) => ( <FormItem> <FormLabel>Question / Prompt *</FormLabel><FormControl><Textarea placeholder="e.g., Based on this company's profile, how well does it fit our ICP for [Product Name]?" rows={4} {...field} /></FormControl><FormDescription>The core instruction for the AI.</FormDescription><FormMessage /></FormItem>)} />
                        {/* Entity Type */}
                        <FormField control={form.control} name="entity_type" render={({ field }) => ( <FormItem> <FormLabel>Applies To *</FormLabel><Select onValueChange={field.onChange} defaultValue={field.value}><FormControl><SelectTrigger><SelectValue placeholder="Select target..." /></SelectTrigger></FormControl><SelectContent><SelectItem value="account">Accounts</SelectItem><SelectItem value="lead">Leads</SelectItem></SelectContent></Select><FormMessage /></FormItem>)} />
                        {/* Response Type */}
                        <FormField control={form.control} name="response_type" render={({ field }) => ( <FormItem> <FormLabel>Response Type *</FormLabel><Select onValueChange={field.onChange} defaultValue={field.value}><FormControl><SelectTrigger><SelectValue placeholder="Select format..." /></SelectTrigger></FormControl><SelectContent><SelectItem value="string">Text</SelectItem><SelectItem value="enum">Multiple Choice (Enum)</SelectItem><SelectItem value="boolean">Yes/No</SelectItem><SelectItem value="number">Number</SelectItem><SelectItem value="json_object">JSON Object</SelectItem></SelectContent></Select><FormMessage /></FormItem>)} />

                        {/* Response Config (Conditional) */}
                        <ResponseConfigInput />
                        <FormField
                            control={form.control}
                            name="ai_config"
                            render={({ field }) => (
                                <FormItem className="flex flex-row items-center space-x-3 space-y-0">
                                    <FormControl>
                                        <Checkbox
                                            checked={field.value?.use_internet === true}
                                            onCheckedChange={(checked) => {
                                                field.onChange({
                                                    ...field.value,
                                                    use_internet: checked
                                                });
                                            }}
                                        />
                                    </FormControl>
                                    <div className="space-y-1 leading-none">
                                        <FormLabel>Internet Access</FormLabel>
                                        <FormDescription>Enable internet access to the AI model.</FormDescription>
                                    </div>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />


                        {/*/!* AI Config *!/*/}
                        {/*<div className="space-y-4 p-4 border rounded-md bg-gray-50">*/}
                        {/*    <FormLabel className="text-base font-semibold">AI Configuration</FormLabel>*/}
                        {/*    <FormField control={form.control} name="ai_config.model" render={({ field }) => ( <FormItem> <FormLabel>AI Model *</FormLabel><Select onValueChange={field.onChange} defaultValue={field.value}><FormControl><SelectTrigger><SelectValue placeholder="Select model..." /></SelectTrigger></FormControl><SelectContent>{AVAILABLE_AI_MODELS.map(m => <SelectItem key={m} value={m}>{m}</SelectItem>)}</SelectContent></Select><FormMessage /></FormItem>)} />*/}
                        {/*    <FormField control={form.control} name="ai_config.temperature" render={({ field }) => ( <FormItem> <FormLabel>Temperature (0-1)</FormLabel><FormControl><Input type="number" step="0.1" min="0" max="1" placeholder="e.g., 0.2" {...field} /></FormControl><FormDescription>Lower values (e.g., 0.1) are more deterministic, higher values (e.g., 0.8) are more creative.</FormDescription><FormMessage /></FormItem>)} />*/}
                        {/*</div>*/}

                        {/*/!* Context Types *!/*/}
                        {/*<FormField*/}
                        {/*    control={form.control}*/}
                        {/*    name="context_type"*/}
                        {/*    render={() => (*/}
                        {/*        <FormItem>*/}
                        {/*            <FormLabel>Required Context *</FormLabel>*/}
                        {/*            <FormDescription>Select the data the AI needs to answer the question.</FormDescription>*/}
                        {/*            <div className="grid grid-cols-2 gap-2 pt-2">*/}
                        {/*                {AVAILABLE_CONTEXT_TYPES.map((item) => (*/}
                        {/*                    <FormField*/}
                        {/*                        key={item.id}*/}
                        {/*                        control={form.control}*/}
                        {/*                        name="context_type"*/}
                        {/*                        render={({ field }) => {*/}
                        {/*                            return (*/}
                        {/*                                <FormItem*/}
                        {/*                                    key={item.id}*/}
                        {/*                                    className="flex flex-row items-start space-x-3 space-y-0"*/}
                        {/*                                >*/}
                        {/*                                    <FormControl>*/}
                        {/*                                        <Checkbox*/}
                        {/*                                            checked={field.value?.includes(item.id)}*/}
                        {/*                                            onCheckedChange={(checked) => {*/}
                        {/*                                                return checked*/}
                        {/*                                                    ? field.onChange([...field.value, item.id])*/}
                        {/*                                                    : field.onChange(*/}
                        {/*                                                        field.value?.filter(*/}
                        {/*                                                            (value) => value !== item.id*/}
                        {/*                                                        )*/}
                        {/*                                                    )*/}
                        {/*                                            }}*/}
                        {/*                                        />*/}
                        {/*                                    </FormControl>*/}
                        {/*                                    <FormLabel className="text-sm font-normal">*/}
                        {/*                                        {item.label}*/}
                        {/*                                    </FormLabel>*/}
                        {/*                                </FormItem>*/}
                        {/*                            )*/}
                        {/*                        }}*/}
                        {/*                    />*/}
                        {/*                ))}*/}
                        {/*            </div>*/}
                        {/*            <FormMessage />*/}
                        {/*        </FormItem>*/}
                        {/*    )}*/}
                        {/*/>*/}

                        {/* Refresh Interval */}
                        {/*<FormField control={form.control} name="refresh_interval" render={({ field }) => ( <FormItem> <FormLabel>Refresh Interval (Hours)</FormLabel><FormControl><Input type="number" placeholder="e.g., 168 (for weekly)" {...field} onChange={event => field.onChange(+event.target.value)} /></FormControl><FormDescription>How often the AI value should be refreshed automatically. Leave blank for no auto-refresh.</FormDescription><FormMessage /></FormItem>)} />*/}
                        {/* Is Active */}
                        <FormField control={form.control} name="is_active" render={({ field }) => (<FormItem className="flex flex-row items-center space-x-3 space-y-0 rounded-md border p-3 shadow-sm bg-gray-50"><FormControl><Checkbox checked={field.value} onCheckedChange={field.onChange} /></FormControl><div className="space-y-1 leading-none"><FormLabel>Active</FormLabel><FormDescription>Enable this column for generation.</FormDescription></div><FormMessage /></FormItem> )} />

                        <DialogFooter>
                            <Button type="button" variant="outline" onClick={() => onOpenChange && onOpenChange(false)} disabled={loading}>Cancel</Button>
                            <Button type="submit" disabled={loading}>
                                {loading ? <ScreenLoader /> : "Create Column"}
                            </Button>
                        </DialogFooter>
                    </form>
                </Form>
            </DialogContent>
        </Dialog>
    );
};

export default CreateCustomColumnDialog;