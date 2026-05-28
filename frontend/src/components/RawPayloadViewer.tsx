import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";

interface Props {
  payload: Record<string, unknown>;
}

export function RawPayloadViewer({ payload }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-md border border-border overflow-hidden">
      <Button
        variant="ghost"
        onClick={() => setOpen((v) => !v)}
        className="w-full justify-between rounded-none border-b border-border px-4 py-2.5 h-auto text-sm font-medium text-muted-foreground hover:bg-muted"
      >
        <span>Raw Source Payload</span>
        {open
          ? <ChevronDown className="h-4 w-4" />
          : <ChevronRight className="h-4 w-4" />
        }
      </Button>

      {open && (
        <ScrollArea className="h-56 bg-neutral-950">
          <pre className="px-4 py-3 text-green-400 text-xs font-mono whitespace-pre-wrap">
            {JSON.stringify(payload, null, 2)}
          </pre>
        </ScrollArea>
      )}
    </div>
  );
}
