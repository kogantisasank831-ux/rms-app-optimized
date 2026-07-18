import { useEffect, useState } from "react";

/** Creates one browser object URL and always revokes it when replaced/unmounted. */
export function useObjectUrl(value: Blob | null): string | null {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!value) {
      setUrl(null);
      return;
    }
    const nextUrl = URL.createObjectURL(value);
    setUrl(nextUrl);
    return () => URL.revokeObjectURL(nextUrl);
  }, [value]);

  return url;
}
