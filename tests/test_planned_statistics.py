"""Known synthetic effects, invalid designs and no mutation of fixed values."""
import copy
import unittest
from gurumoji.services.statistical_tests import run_statistics


class PlannedStatisticsTests(unittest.TestCase):
    def variables(self, **levels):
        return [dict(column=key, measurement_level=level,source='rule',validation_status='validated',unit='row',definition_version=1)
                for key,level in levels.items()]

    def run_plan(self, values, variables, **plan):
        table={'fields':list(values[0]),'rows':[{'row_id':f'r{i}','values':row} for i,row in enumerate(values)]}
        before=copy.deepcopy(table)
        result=run_statistics(table,variables,{'analysis_unit':'row','outcome':'y','min_n':5,**plan})
        self.assertEqual(table,before)
        return result['results'][0]

    def test_descriptive_zero_and_missing_have_distinct_denominators(self):
        result=self.run_plan([{'y':y} for y in [0,1,2,3,4,None]],self.variables(y='ratio'),method='descriptive')
        self.assertEqual((result['n'],result['input_rows'],result['missing_rows']),(5,6,1))
        self.assertEqual(result['mean'],2)

    def test_known_welch_shift_and_confidence_interval(self):
        values=[{'y':i,'g':'A'} for i in range(1,11)]+[{'y':i+10,'g':'B'} for i in range(1,11)]
        result=self.run_plan(values,self.variables(y='ratio',g='nominal'),group='g',method='auto')
        self.assertEqual(result['method'],'welch')
        self.assertEqual(result['status'],'completed')
        self.assertAlmostEqual(result['statistic'],-7.385489458759964,places=8)
        self.assertLess(result['ci_high'],0)
        self.assertLess(result['p_adjusted'],.00001)

    def test_confirmation_and_utterance_independence_fail_before_calculation(self):
        table={'fields':['y'],'rows':[{'values':{'y':i}} for i in range(10)]}
        variables=self.variables(y='ratio'); variables[0]['validation_status']='unvalidated'
        with self.assertRaises(ValueError):
            run_statistics(table,variables,{'outcome':'y','analysis_unit':'row','mode':'confirmatory','preregistered':True})
        with self.assertRaises(ValueError):
            run_statistics(table,variables,{'outcome':'y','analysis_unit':'utterance','method':'one_sample','reference':0})

    def test_linear_coefficients_and_sparse_fisher(self):
        values=[{'x':i,'y':3+2*i+(.1 if i%2 else -.1)} for i in range(20)]
        result=self.run_plan(values,self.variables(x='ratio',y='ratio'),method='linear',predictors=['x'])
        self.assertEqual(result['status'],'completed')
        self.assertAlmostEqual(result['coefficients'][1]['estimate'],2,places=2)
        values=[{'g':'A','y':'yes'} for _ in range(5)]+[{'g':'B','y':'no'} for _ in range(5)]
        result=self.run_plan(values,self.variables(g='nominal',y='nominal'),method='chi_square',group='g')
        self.assertEqual(result['method'],'fisher_exact')
        self.assertEqual(result['status'],'completed')

    def test_group_aggregation_keeps_source_row_ids_and_rejects_mixed_groups(self):
        rows=[{'values':{'who':str(i//2),'g':'A','y':i},'row_id':str(i)} for i in range(10)]
        table={'fields':['who','g','y'],'rows':rows}
        plan={'outcome':'y','method':'descriptive','analysis_unit':'speaker','unit_column':'who','group':'g','min_n':5}
        result=run_statistics(table,self.variables(who='nominal',g='nominal',y='ratio'),plan)
        self.assertEqual(result['results'][0]['n'],5)
        self.assertEqual(result['analysis_rows'][0]['_source_rows'],['0','1'])
        table['rows'][1]['values']['g']='B'
        with self.assertRaises(ValueError): run_statistics(table,self.variables(who='nominal',g='nominal',y='ratio'),plan)
