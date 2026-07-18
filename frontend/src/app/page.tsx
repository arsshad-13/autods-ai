import { getHealth } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

export default async function Home() {
  let healthData = null;
  let error = null;

  try {
    healthData = await getHealth();
  } catch (e: any) {
    error = e.message;
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24 bg-muted/20">
      <div className="z-10 w-full max-w-md items-center justify-between font-mono text-sm">
        <Card>
          <CardHeader>
            <CardTitle className="text-2xl text-center">AutoDS AI</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="font-semibold">API Status</span>
              {error ? (
                <Badge variant="destructive">Error</Badge>
              ) : (
                <Badge variant={healthData?.status === 'ok' ? 'default' : 'destructive'}>
                  {healthData?.status || 'Unknown'}
                </Badge>
              )}
            </div>
            
            <div className="flex justify-between items-center">
              <span className="font-semibold">Database</span>
              <Badge variant={healthData?.database === 'connected' ? 'default' : 'destructive'}>
                {healthData?.database || 'Unreachable'}
              </Badge>
            </div>

            <div className="flex justify-between items-center">
              <span className="font-semibold">Version</span>
              <span className="text-muted-foreground">{healthData?.version || '-'}</span>
            </div>

            <div className="flex justify-between items-center">
              <span className="font-semibold">Environment</span>
              <span className="text-muted-foreground">{healthData?.environment || '-'}</span>
            </div>

            {error && (
              <div className="mt-4 p-3 bg-destructive/10 text-destructive rounded text-xs break-all">
                {error}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
