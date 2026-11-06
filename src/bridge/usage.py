"""Read-only projection of the signed-in desktop account's quota windows."""
import datetime as dt
import math

def number(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)

def usage_view(value):
    by_id=value.get('rateLimitsByLimitId')
    buckets=list(by_id.values()) if isinstance(by_id,dict) and by_id else ([value['rateLimits']] if isinstance(value.get('rateLimits'),dict) else [])
    groups=[]
    for bucket in buckets:
        if not isinstance(bucket,dict):continue
        windows=[]
        for key in ('primary','secondary'):
            window=bucket.get(key)
            if not isinstance(window,dict):continue
            used=window.get('usedPercent');duration=window.get('windowDurationMins');reset=window.get('resetsAt')
            windows.append({'usedPercent':round(max(0,min(100,used)),2) if number(used) else None,
                            'remainingPercent':round(max(0,min(100,100-used)),2) if number(used) else None,
                            'windowDurationMins':duration if number(duration) and duration>0 else None,
                            'resetsAt':reset if number(reset) and reset>0 else None})
        credits=bucket.get('credits')
        groups.append({'name':bucket.get('limitName') or ('Codex' if bucket.get('limitId') in (None,'codex') else bucket['limitId']),
                       'planType':bucket.get('planType'),'windows':windows,
                       'limitReached':bool(bucket.get('rateLimitReachedType') or bucket.get('spendControlReached')),
                       'credits':{'unlimited':bool(credits.get('unlimited')),'balance':str(credits['balance']) if credits.get('balance') is not None else None,'hasCredits':credits.get('hasCredits')} if isinstance(credits,dict) else None})
    resets=value.get('rateLimitResetCredits') or {}
    count=resets.get('availableCount')
    return {'groups':groups,'ordinaryUsageAllowed':value.get('ordinaryUsageAllowed'),
            'availableResetCount':count if isinstance(count,int) and not isinstance(count,bool) and count>=0 else None,
            'updatedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'stale':False}
