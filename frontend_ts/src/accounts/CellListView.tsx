// Component that displays given list of values
// in a table cell.
const CellListView: React.FC<{ values: string[] }> = ({ values }) => {
  return (
    <div className="flex flex-col gap-1">
      {values.map((value) => (
        <p key={value}>{value}</p>
      ))}
    </div>
  );
};

export default CellListView;
