import unittest
from usage import usage_view

class UsageTests(unittest.TestCase):
    def test_account_with_only_weekly_window_does_not_invent_five_hour_limit(self):
        v=usage_view({'rateLimitsByLimitId':{'codex':{'limitId':'codex','planType':'prolite','primary':{'usedPercent':53,'windowDurationMins':10080,'resetsAt':1793988152},'secondary':None}}})
        windows=v['groups'][0]['windows']
        self.assertEqual(len(windows),1);self.assertEqual(windows[0]['remainingPercent'],47);self.assertEqual(windows[0]['windowDurationMins'],10080)
    def test_multiple_buckets_preferred_to_legacy_bucket(self):
        v=usage_view({'rateLimits':{'limitId':'old'},'rateLimitsByLimitId':{'codex':{'limitId':'codex','primary':{'usedPercent':25,'windowDurationMins':300}},'extra':{'limitId':'extra','limitName':'Extra model','primary':{'usedPercent':10}}}})
        self.assertEqual([g['name'] for g in v['groups']],['Codex','Extra model'])
        self.assertEqual(v['groups'][0]['windows'][0]['remainingPercent'],75)
    def test_missing_values_remain_unknown_instead_of_zero(self):
        v=usage_view({'rateLimits':{'primary':{'usedPercent':None,'windowDurationMins':None,'resetsAt':None},'credits':{'balance':None}}})
        w=v['groups'][0]['windows'][0]
        self.assertIsNone(w['remainingPercent']);self.assertIsNone(w['usedPercent']);self.assertIsNone(w['resetsAt']);self.assertIsNone(v['groups'][0]['credits']['balance'])
    def test_percent_is_clamped_without_inverting_used_and_remaining(self):
        for used,left in [(0,100),(25.5,74.5),(100,0),(120,0),(-5,100)]:
            v=usage_view({'rateLimits':{'primary':{'usedPercent':used}}})
            self.assertEqual(v['groups'][0]['windows'][0]['remainingPercent'],left)
    def test_unknown_data_does_not_include_account_or_reset_token_ids(self):
        v=usage_view({'accountId':'private-account','rateLimitResetCredits':{'availableCount':2,'credits':[{'id':'opaque-reset-token'}]}})
        self.assertEqual(v['groups'],[]);self.assertEqual(v['availableResetCount'],2)
        self.assertNotIn('private-account',str(v));self.assertNotIn('opaque-reset-token',str(v))
