export interface CustomColumnValueData {
    name: string;
    description: string | null;
    question: string | null;
    value: string | number | boolean | object | null; // The actual AI-generated value
    confidence: number | null;
    rationale: string | null;
    generated_at: string; // ISO date string
    response_type: 'string' | 'json_object' | 'boolean' | 'number' | 'enum';
}