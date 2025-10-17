export default function PipelineExtension({
  pipelineId,
}: {
  pipelineId: string;
}) {
  return (
    <>
      <div>
        <h1>Extensions {pipelineId}</h1>
      </div>
    </>
  );
}
