# %%
import numpy as np
import pandas as pd
%load_ext google.cloud.bigquery

# %% 
## %%bigquery covariates
# select sample_id, FieldID, instance, value from `ukbb7089_202006.phenotype` 
# where FieldID = 21001 -- bmi
# or FieldID = 21003 -- age at assessment
# or FieldID = 22001 -- genetic sex
# or FieldID = 31 -- sex
# or FieldID = 30690 -- cholesterol
# or FieldID = 30760 -- HDL cholesterol
# or FieldID = 20116 -- smoking
# or FieldID = 4079 -- diastolic bp
# or FieldID = 4080 -- systolic bp
# or FieldID = 95 -- pulse rate
# or FieldID = 53 -- instance 0 date
# or FieldID = 30700 -- creatinine
# # %%
# covariates.to_csv('bq_covariates.tsv', sep='\t')

# # %%
# %%bigquery race
# select sample_id, FieldID, instance, value from `ukbb7089_202006.phenotype` 
# where FieldID = 21000 -- race
# # %%
# race.to_csv('bq_race.tsv', sep='\t')

# %%
# %%bigquery diseases
# select disease, sample_id, incident_disease, prevalent_disease, censor_date from `ukbb7089_202006.disease` 
# where has_disease > 0.5

# # %%
# diseases.to_csv('bq_diseases.tsv', sep='\t')
# %%


# %%
covariates = pd.read_csv('bq_covariates.tsv', sep='\t')
race = pd.read_csv('bq_race.tsv', sep='\t')
drugs = pd.read_csv('common.csv', sep='\t', usecols=['sample_id', 'c_lipidlowering', 'c_antihypertensive'])
covariates = pd.concat([covariates, race])
diseases = pd.read_csv('bq_diseases.tsv', sep='\t')
diseases['censor_date'] = pd.to_datetime(diseases['censor_date'])

# %%
pretest = pd.read_csv('pretest_inference_60k.tsv', sep='\t')
pretest_old = pd.read_csv('pretest_results_for_bolt.tsv', '\t')
pretest_old['sample_id'] = pretest_old['FID']
pretest_to_rest = pd.read_csv('/mnt/disks/pd-nd-hrr-results/rest_model_inference.tsv', sep='\t').drop(columns=['50_hrr_actual'])
resting = pd.read_csv('exp_resting_hr.csv', sep=',')
resting['sample_id'] = resting['fpath'].str.split('/').str[-1].str.replace('.hd5', '').apply(int)
resting = resting[['sample_id', 'resting_hr']]
pretest = pretest.merge(resting, on='sample_id')
# pretest = pretest.merge(pretest_old, on='sample_id', suffixes=('', '_old'))
pretest_to_rest_overlap = pretest.merge(pretest_to_rest, on='sample_id')
all_ecgs = pd.concat([pretest]).dropna()
all_ecgs = all_ecgs.merge(drugs, on='sample_id', how='left')
all_ecgs = all_ecgs.fillna(0)
pretest_to_rest = pretest_to_rest.merge(drugs, on='sample_id', how='left')
pretest_to_rest = pretest_to_rest.fillna(0)
pretest_to_rest_overlap = pretest_to_rest_overlap.merge(drugs, on='sample_id', how='left')
pretest_to_rest_overlap = pretest_to_rest_overlap.fillna(0)

ecg_sets = [all_ecgs, pretest_to_rest, pretest_to_rest_overlap]
# %%
pheno_dic = {
             21003: ['age', float],
             31: ['male', int],
             21000: ['nonwhite', int],
             21001: ['bmi', float],
             30690: ['cholesterol', float],
             30760: ['HDL', float],
             4079: ['diastolic_bp', int],
             4080: ['systolic_bp', int],
             20116: ['current_smoker', int],
             30700: ['creatinine', float],
             53: ['instance0_date', pd.to_datetime]
            }


for i, ecg_set in enumerate(ecg_sets):
    missing = []
    for pheno in pheno_dic:
        tmp_covariates = covariates[(covariates['FieldID']==pheno) &\
                                    (covariates['instance']==0)]
        if pheno == 53:
            tmp_covariates['value'] = pd.to_datetime(tmp_covariates['value'])
        else:
            tmp_covariates['value'] = tmp_covariates['value'].apply(pheno_dic[pheno][1])
        if (pheno == 4079) or (pheno == 4080):
            tmp_covariates = tmp_covariates[['sample_id', 'value']].groupby('sample_id').mean().reset_index(level=0)
        
        ecg_sets[i] = ecg_sets[i].merge(tmp_covariates[['sample_id', 'value']], left_on=['sample_id'], right_on=['sample_id'], how='inner')
        ecg_sets[i][pheno_dic[pheno][0]] = ecg_sets[i]['value']
        ecg_sets[i] = ecg_sets[i].drop(columns=['value'])
        missing.append(ecg_sets[i][pheno_dic[pheno][0]].isna().sum())
        print(ecg_sets[i][pheno_dic[pheno][0]].isna().sum())
    ecg_sets[i]['nonwhite'] = (ecg_sets[i]['nonwhite'] != 1001).apply(float)
    ecg_sets[i]['current_smoker'] = (ecg_sets[i]['current_smoker'] == 2).apply(float)
    ecg_sets[i]
    missing = pd.DataFrame({'missing': missing})
    missing

# %%
def gfr(x):
    k = 0.7 + 0.2*x['male']
    alpha = -0.329 - 0.082*x['male']
    f1 = x['creatinine']/88.4/k
    f1[f1>1.0] = 1.0
    f2 = x['creatinine']/88.4/k
    f2[f2<1.0] = 1.0
    
    gfr = 141.0 * f1**alpha \
          *f2**(-1.209) \
          *0.993**x['male'] \
          *(1.0+0.018*(1.0-x['male']))
        
    return gfr

for i, ecg_set in enumerate(ecg_sets):
    ecg_sets[i]['gfr'] = gfr(ecg_sets[i])

# %%
all_ecgs, pretest_to_rest, pretest_to_rest_overlap = ecg_sets
all_ecgs  = pretest_to_rest_overlap
# %%
%matplotlib inline
import matplotlib.pyplot as plt
f, ax = plt.subplots()
f.set_size_inches(16, 9)
all_ecgs.hist(ax=ax)
plt.tight_layout()

# %% 
# Phenotype plots
import matplotlib.pyplot as plt
import seaborn as sns

f, axs = plt.subplots(ncols=1, sharey=True, figsize=(4, 3))
f.subplots_adjust(hspace=0.5, left=0.07, right=0.93)
ax = axs
hb = ax.hexbin(all_ecgs['50_hrr_actual'], all_ecgs['50_hrr_downsample_augment_prediction'],  mincnt=1, cmap='gray')
ax.set_ylabel('HRR50 (bpm)')
ax.set_xlabel('HRR50-rest (bpm)')
ax.set_aspect('equal')
ax.set_ylim([-5, 60])
ax.set_ylim([-5, 60])
cb = f.colorbar(hb, ax=ax)
cb.set_label('counts')
plt.tight_layout()
f.savefig('correlation_overlap.png', dpi=500)
# ax[1].hexbin(all_ecgs['resting_hr'], all_ecgs['50_hrr_actual'], mincnt=1)
# ax[1].set_ylabel('HRR (bpm)')
# ax[1].set_xlabel('resting HR (bpm)')
# ax[1].set_xlim([-5, 150])
# ax[1].set_ylim([-5, 60])
ax.set_title(f"r={np.corrcoef(all_ecgs.dropna()['50_hrr_actual'], all_ecgs.dropna()['resting_hr'])[0, 1]}")

f, ax = plt.subplots()
f.set_size_inches(3.5, 3)
sns.distplot(all_ecgs['50_hrr_actual'], ax=ax, kde=False, color='gray', label='HRR50')
sns.distplot(all_ecgs['50_hrr_downsample_augment_prediction'], ax=ax, kde=False, color='black', label='HRR50-rest')
ax.set_xlabel('HRR (actual vs predicted) (bpm)')
ax.legend(loc='upper left')
plt.tight_layout()
f.savefig('distribution_overlap.png', dpi=500)

# all_ecgs['HRR50'] = all_ecgs['50_hrr_actual']
# all_ecgs['HR-pretest'] = all_ecgs['resting_hr']
# all_ecgs['HRR50-restHR_age_sex_bmi'] = all_ecgs['pretest_baseline_model_50_hrr_predicted']
# all_ecgs['HRR50-pretest'] = all_ecgs['pretest_model_50_hrr_predicted']
# all_ecgs['HRR50-pretest_age_sex_bmi'] = all_ecgs['pretest_model_50_hrr_predicted_old']
# all_ecgs['HRR50-pretest-maxHR_age_sex_bmi'] = all_ecgs['pretest_hr_achieved_model_50_hrr_predicted']
# all_ecgs['HRR50-pretest-075maxHR_age_sex_bmi'] = all_ecgs['pretest_hr_achieved_model_50_hrr_predicted_75_hr_achieved']
# all_ecgs['HR-pretest'] = all_ecgs['resting_hr']
# f, ax = plt.subplots()
# f.set_size_inches(6.5, 5)
# sns.heatmap(np.abs(all_ecgs.dropna()[['HRR50', 'HR-pretest',  
#                                       'HRR50-pretest', 'HRR50-restHR_age_sex_bmi', 'HRR50-pretest_age_sex_bmi', 
#                                       'HRR50-pretest-maxHR_age_sex_bmi', 
#                                       'HRR50-pretest-075maxHR_age_sex_bmi']].corr().round(2)),
#             annot=True, cmap='gray', ax=ax)
# ax.set_xticklabels(['HRR50', 'HR-pretest',  
#                     'HRR50-pretest', 'HRR50-restHR_age_sex_bmi', 'HRR50-pretest_age_sex_bmi', 
#                     'HRR50-pretest-maxHR_age_sex_bmi', 
#                     'HRR50-pretest-075maxHR_age_sex_bmi'], rotation=45, ha='right')
# plt.tight_layout()
# f.savefig('intercorrlations.png', dpi=500)


# %%
disease_list = [
    'Atrial_fibrillation_or_flutter_v2',
'Bradyarrhythmia_general_inclusive_definition',
'Cardiac_surgery',
'Congenital_heart_disease',
'Coronary_Artery_Disease_SOFT',
'DCM_I42',
'Diabetes_Type_1',
'Diabetes_Type_2',
'Heart_Failure_V2',
'Hypertension',
'Myocardial_Infarction',
'Peripheral_vascular_disease',
'Pulmonary_Hypertension',
'Sarcoidosis',
'Stroke',
'Supraventricular_arrhythmia_General_inclusive_definition',
'Venous_thromboembolism',
'composite_af_chf_dcm_death',
'composite_cad_dcm_hcm_hf_mi',
'composite_chf_dcm_death',
'composite_mi_cad_stroke',
'composite_mi_cad_stroke_death',
'composite_mi_cad_stroke_death_exclude_AML',
'composite_mi_cad_stroke_death_exclude_anycancer',
'composite_mi_cad_stroke_death_exclude_heme',
'composite_mi_cad_stroke_exclude_heme',
'composite_mi_cad_stroke_hf',
'composite_mi_death']

disease_list = [['Heart_Failure_V2', 'heart failure'], 
                ['Myocardial_Infarction', 'myocardial infarction'],
                ['Atrial_fibrillation_or_flutter_v2', 'atrial fibrillation'], 
                ['Diabetes_Type_2', 'type 2 diabetes'],
                ['Hypertension', 'hypertension'],                
                ['composite_af_chf_dcm_death', 'AF+CHF+DCM+death'],
                ['composite_cad_dcm_hcm_hf_mi', 'CAD+DCM+HCM+HF+MI'],
                ['composite_chf_dcm_death', 'CHF+DCM+death']]

disease_list = [['Heart_Failure_V2', 'heart failure'], 
                ['Diabetes_Type_2', 'type 2 diabetes'],
                ]

# %%
diseases_unpack = pd.DataFrame()
diseases_unpack['sample_id'] = np.unique(np.hstack([diseases['sample_id'], all_ecgs['sample_id']]))
for disease, disease_label in disease_list:
    tmp_diseases = diseases[(diseases['disease']==disease) &\
                            (diseases['incident_disease'] > 0.5)]
    tmp_diseases_unpack = diseases_unpack.merge(tmp_diseases[['sample_id', 'incident_disease', 'censor_date']], how='left', on='sample_id')
    diseases_unpack[f'{disease}_incident'] = tmp_diseases_unpack['incident_disease']
    diseases_unpack[f'{disease}_censor_date'] = tmp_diseases_unpack['censor_date']
    tmp_diseases = diseases[(diseases['disease']==disease) &\
                             (diseases['prevalent_disease'] > 0.5)]
    tmp_diseases_unpack = diseases_unpack.merge(tmp_diseases[['sample_id', 'prevalent_disease', 'censor_date']], how='left', on='sample_id')
    diseases_unpack[f'{disease}_prevalent'] = tmp_diseases_unpack['prevalent_disease']
    diseases_unpack[f'{disease}_censor_date'] = tmp_diseases_unpack['censor_date']
    diseases_unpack.loc[diseases_unpack[f'{disease}_censor_date'].isna(), f'{disease}_censor_date'] = pd.to_datetime('2017-03-31')
#     tmp_diseases = diseases[(diseases['disease']==disease) &\
#                             (diseases['has_disease'] < 0.5)]
#     tmp_diseases_unpack = diseases_unpack.merge(tmp_diseases[['sample_id', 'prevalent_disease', 'censor_date']], how='left', on='sample_id')
#     diseases_unpack[f'{disease}_censor_date'] = tmp_diseases_unpack['censor_date']

# %%
diseases_unpack = diseases_unpack.fillna(0)
all_ecgs = all_ecgs.dropna()

# %%
label_dic = {
    '50_hrr_actual': ['HRR50', 'beats'],
    'resting_hr': ['HR-pretest', 'beats'],
    'pretest_model_50_hrr_predicted': ['HRR50-pretest', 'beats'],
    '50_hrr_downsample_augment_prediction': ['HRR50-rest', 'beats'],
    'age': ['Age', 'yrs'],
    'male': ['Male', ''],
    'nonwhite': ['Nonwhite', ''],
    'bmi': ['BMI', 'units'],
    'cholesterol': ['Cholesterol', 'mmol/L'],
    'HDL': ['HDL', 'mmol/L'],
    'current_smoker': ['Current smoker', ''],
    'diastolic_bp': ['Diastolic blood pressure', 'mmHg'],
    'systolic_bp': ['Systolic blood pressure', 'mmHg'],   
    'gfr': ['eGFR', 'mL/min/1.73 m2'],
    'creatinine': ['Creatinine', 'umol/L'],
    'c_lipidlowering': ['Lipid lowering drugs', ''],
    'c_antihypertensive': ['Antihypertensive drugs', '']
}

# %%
# scaled
import statsmodels.api as sm
or_dic = {}
for pheno in all_ecgs:
    if pheno in ['instance0_date', 'sample_id', 'FID', 'IID', '50_hrr']: 
        continue
    or_dic[pheno] = {}
    tmp_pheno = all_ecgs[['sample_id', pheno]]
    for disease, disease_label in disease_list:
        for occ in ['prevalent']:
            or_dic[pheno][f'{disease}_{occ}'] = {}
            tmp_data = tmp_pheno.merge(diseases_unpack[['sample_id', f'{disease}_{occ}']], left_on='sample_id', right_on='sample_id')
            if pheno not in ['male', 'nonwhite', 'current_smoker', 'c_lipidlowering', 'c_antihypertensive']:
                std = np.std(tmp_data[pheno].values)
                tmp_data[pheno] = (tmp_data[pheno].values - np.mean(tmp_data[pheno].values))/std
                std = ", %.1f" % std
            else:
                std = ''
            tmp_data['intercept'] = 1.0
            res = sm.Logit(tmp_data[f'{disease}_{occ}'], tmp_data[[pheno, 'intercept']]).fit(disp=False)
            or_dic[pheno][f'{disease}_{occ}']['OR'] = np.exp(res.params[0])
            or_dic[pheno][f'{disease}_{occ}']['CI'] = np.exp(res.conf_int().values[0])
            or_dic[pheno][f'{disease}_{occ}']['p'] = res.pvalues[pheno]
            or_dic[pheno][f'{disease}_{occ}']['n'] = np.sum(tmp_data[f'{disease}_{occ}'])
            or_dic[pheno][f'{disease}_{occ}']['std'] = std

# %%
%matplotlib inline
import matplotlib.pyplot as plt
import matplotlib
dis_plot_list = disease_list
phenos = or_dic['50_hrr_actual'].keys()
for dis, dis_label in disease_list:
    for occ in ['prevalent']: 
        ors = []
        cis_minus = []
        cis_plus = []
        labels = []
        for pheno in or_dic:
            if 'genetic' in pheno: 
                continue
            if 'hrr' in pheno:
                scale = 1.0
            elif 'age' in pheno:
                scale = 1.0
            else:
                scale = 1.0
            ors.append(np.exp(np.log(or_dic[pheno][f'{dis}_{occ}']['OR'])*scale))
            cis_minus.append(np.exp(np.log(or_dic[pheno][f'{dis}_{occ}']['OR']-or_dic[pheno][f'{dis}_{occ}']['CI'][0])*scale))
            cis_plus.append(np.exp(np.log(or_dic[pheno][f'{dis}_{occ}']['CI'][1]-or_dic[pheno][f'{dis}_{occ}']['OR'])*scale))      
            labels.append(f'{label_dic[pheno][0]}{or_dic[pheno][dis+"_"+occ]["std"]} {label_dic[pheno][1]}')
            if or_dic[pheno][f'{dis}_{occ}']['p'] < (0.05/len(or_dic)):
                labels[-1] += '*'
        f, ax = plt.subplots()
        f.set_size_inches(6, 4)
        ax.errorbar(ors, np.arange(len(ors)), xerr=(cis_minus, cis_plus), marker='o', linestyle='', color='black')  
        ax.plot([1.0, 1.0], [-1.0, len(ors)], 'k--')
        ax.set_yticks(np.arange(len(ors)))
        ax.set_yticklabels(labels)
        ax.set_xscale('log', basex=np.exp(1))   
        ax.set_xticks([0.25, 0.5, 1.0, 2.0, 4.0, 8.0])
        ax.set_xticklabels(map(str, [0.25, 0.5, 1.0, 2.0, 4.0, 8.0]))
#         locmin = matplotlib.ticker.LogLocator(base=np.exp(1),subs=(0.3,0.35,0.4,0.45,
#                                                                0.6,0.7,0.8,0.9,
#                                                                1.2,1.4,1.6,1.8,
#                                                                2.4,2.8,3.2,3.6))
#         ax.xaxis.set_minor_locator(locmin)
#         ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
        #ax.set_xticks(np.logspace(-0.1, 8, 6, base=np.exp(1)))
        #ax.set_xticklabels(["%.2f" %d for d in np.exp(np.arange(-0.5, 2.1, 0.5))])
        ax.set_xlabel('Odds ratio (per 1-SD increase)')
        ax.set_title(f'{occ} {dis_label}\n n$_+$ = {int(or_dic[pheno][dis+"_"+occ]["n"])} / {len(all_ecgs)}')
        ax.set_ylim([-1.0, len(ors)])
        ax.set_xlim([0.25, 10.0])
        plt.tight_layout()
        f.savefig(f'{dis}_{occ}_or_overlap.png', dpi=500)

# %%
# scaled
import statsmodels.api as sm
hr_dic = {}
for pheno in all_ecgs:
    if pheno in ['instance0_date', 'sample_id', 'FID', 'IID', '50_hrr']: 
        continue
    hr_dic[pheno] = {}
    tmp_pheno = all_ecgs[['sample_id', pheno, 'instance0_date']]
    for disease, disease_label in disease_list:
        for occ in ['incident']:
            hr_dic[pheno][f'{disease}_{occ}'] = {}
            tmp_data = tmp_pheno.merge(diseases_unpack[['sample_id', f'{disease}_{occ}', f'{disease}_censor_date']], left_on='sample_id', right_on='sample_id')
            if pheno not in ['male', 'nonwhite', 'current_smoker', 'c_lipidlowering', 'c_antihypertensive']:
                std = np.std(tmp_data[pheno].values)
                tmp_data[pheno] = (tmp_data[pheno].values - np.mean(tmp_data[pheno].values))/std
                std = ", %.1f" % std
            else:
                std = ''
            tmp_data['futime'] = (tmp_data[f'{disease}_censor_date']-tmp_data['instance0_date']).dt.days
            tmp_data['entry'] = 0.0
            tmp_data['intercept'] = 1.0
            tmp_data = tmp_data[tmp_data['futime']>0]
            res = sm.PHReg(tmp_data['futime'], tmp_data[pheno], 
                           tmp_data[f'{disease}_{occ}'], tmp_data['entry']).fit()
            hr_dic[pheno][f'{disease}_{occ}']['HR'] = np.exp(res.params[0])
            hr_dic[pheno][f'{disease}_{occ}']['CI'] = np.exp(res.conf_int()[0])
            hr_dic[pheno][f'{disease}_{occ}']['p'] = res.pvalues[0]
            hr_dic[pheno][f'{disease}_{occ}']['n'] = np.sum(tmp_data[f'{disease}_{occ}'])
            hr_dic[pheno][f'{disease}_{occ}']['std'] = std

# %%
dis_plot_list = disease_list
phenos = hr_dic['50_hrr_actual'].keys()
for dis, dis_label in disease_list:
    for occ in ['incident']:
        hrs = []
        cis_minus = []
        cis_plus = []
        labels = []
        for pheno in hr_dic:
            if 'genetic' in pheno: 
                continue
            if 'hrr' in pheno:
                scale = 1.0
            elif 'age' in pheno:
                scale = 1.0
            else:
                scale = 1.0
            hrs.append(np.exp(np.log(hr_dic[pheno][f'{dis}_{occ}']['HR'])*scale))
            cis_minus.append(np.exp(np.log(hr_dic[pheno][f'{dis}_{occ}']['HR']-hr_dic[pheno][f'{dis}_{occ}']['CI'][0])*scale))
            cis_plus.append(np.exp(np.log(hr_dic[pheno][f'{dis}_{occ}']['CI'][1]-hr_dic[pheno][f'{dis}_{occ}']['HR'])*scale))      
            labels.append(f'{label_dic[pheno][0]}{hr_dic[pheno][dis+"_"+occ]["std"]} {label_dic[pheno][1]}')
            if hr_dic[pheno][f'{dis}_{occ}']['p'] < (0.05/len(hr_dic)):
                labels[-1] += '*'
        f, ax = plt.subplots()
        f.set_size_inches(3.3, 4)
        ax.errorbar(hrs, np.arange(len(hrs)), xerr=(cis_minus, cis_plus), marker='o', linestyle='', color='black')    
        ax.set_yticks(np.arange(len(hrs)))
        ax.set_yticklabels(labels)
        ax.set_yticklabels([])
        ax.set_xscale('log', basex=np.exp(1))  
        ax.plot([1.0, 1.0], [-1.0, len(hrs)], 'k--')
        ax.set_xticks([0.25, 0.5, 1.0, 2.0, 4.0, 8.0])
        ax.set_xticklabels(map(str, [0.25, 0.5, 1.0, 2.0, 4.0, 8.0]))
        ax.set_ylim([-1.0, len(hrs)])
        ax.set_xlim([0.25, 10.0])
        ax.set_xlabel('Hazard ratio (per 1-SD increase)')
        ax.set_title(f'{occ} {dis_label}\n n$_+$ = {int(hr_dic[pheno][dis+"_"+occ]["n"])} / {len(all_ecgs)}')
        plt.tight_layout()
        f.savefig(f'{dis}_{occ}_hr_overlap.png', dpi=500)

# %%
# scaled
import statsmodels.api as sm
or_multi_dic = {}
covariates = ['bmi', 'age', 'male', 'cholesterol', 'HDL', 'current_smoker',
              'diastolic_bp', 'systolic_bp', 'c_lipidlowering', 'c_antihypertensive']
covariates_scale = ['bmi', 'age', 'cholesterol', 'HDL',
                    'diastolic_bp', 'systolic_bp']
for pheno in ['50_hrr_actual', 'pretest_model_50_hrr_predicted', 'resting_hr', '50_hrr_downsample_augment_prediction']:
    if pheno in ['FID', 'IID', 'instance0_date']: 
        continue
    or_multi_dic[pheno] = {}
    tmp_pheno = all_ecgs[['sample_id', pheno] + covariates]
    for disease, disease_label in disease_list:
        for occ in ['incident', 'prevalent']:
            or_multi_dic[pheno][f'{disease}_{occ}'] = {}
            tmp_data = tmp_pheno.merge(diseases_unpack[['sample_id', f'{disease}_{occ}']], left_on='sample_id', right_on='sample_id')
            std = np.std(tmp_data[pheno].values)
            tmp_data[pheno] = (tmp_data[pheno].values - np.mean(tmp_data[pheno].values))/std
            std = ", %.1f" % std
            tmp_data[covariates_scale] = (tmp_data[covariates_scale].values \
                                          - np.mean(tmp_data[covariates_scale].values, axis=0))/\
                                          np.std(tmp_data[covariates_scale].values, axis=0)
            tmp_data['intercept'] = 1.0
            res = sm.Logit(tmp_data[f'{disease}_{occ}'], tmp_data[[pheno, 'intercept']+covariates]).fit()
            or_multi_dic[pheno][f'{disease}_{occ}']['OR'] = np.exp(res.params[0])
            or_multi_dic[pheno][f'{disease}_{occ}']['CI'] = np.exp(res.conf_int().values[0])
            or_multi_dic[pheno][f'{disease}_{occ}']['p'] = res.pvalues[pheno]
            or_multi_dic[pheno][f'{disease}_{occ}']['n'] = np.sum(tmp_data[f'{disease}_{occ}'])
            or_multi_dic[pheno][f'{disease}_{occ}']['std'] = std

# %%
%matplotlib inline
import matplotlib.pyplot as plt
import matplotlib
dis_plot_list = disease_list
phenos = or_multi_dic['50_hrr_actual'].keys()
for dis, dis_label in disease_list:
    for occ in ['prevalent']: 
        ors = []
        cis_minus = []
        cis_plus = []
        labels = []
        for pheno in or_multi_dic:
            if 'genetic' in pheno: 
                continue
            if 'hrr' in pheno:
                scale = 1.0
            elif 'age' in pheno:
                scale = 1.0
            else:
                scale = 1.0
            ors.append(np.exp(np.log(or_multi_dic[pheno][f'{dis}_{occ}']['OR'])*scale))
            cis_minus.append(np.exp(np.log(or_multi_dic[pheno][f'{dis}_{occ}']['OR']-or_multi_dic[pheno][f'{dis}_{occ}']['CI'][0])*scale))
            cis_plus.append(np.exp(np.log(or_multi_dic[pheno][f'{dis}_{occ}']['CI'][1]-or_multi_dic[pheno][f'{dis}_{occ}']['OR'])*scale))      
            labels.append(f'{label_dic[pheno][0]}{or_multi_dic[pheno][dis+"_"+occ]["std"]} {label_dic[pheno][1]}')
            if or_dic[pheno][f'{dis}_{occ}']['p'] < (0.05/len(or_dic)):
                labels[-1] += '*'
        f, ax = plt.subplots()
        f.set_size_inches(6, 3)
        ax.errorbar(ors, np.arange(len(ors)), xerr=(cis_minus, cis_plus), marker='o', linestyle='', color='black')  
        ax.plot([1.0, 1.0], [-1.0, len(ors)], 'k--')
        ax.set_yticks(np.arange(len(ors)))
        ax.set_yticklabels(labels)
        ax.set_xscale('log', basex=np.exp(1))   
        ax.set_xticks([0.4, 0.8, 1.6])
        ax.set_xticklabels(map(str, [0.4, 0.8, 1.6]))
#         locmin = matplotlib.ticker.LogLocator(base=np.exp(1),subs=(0.3,0.35,0.4,0.45,
#                                                                0.6,0.7,0.8,0.9,
#                                                                1.2,1.4,1.6,1.8,
#                                                                2.4,2.8,3.2,3.6))
#         ax.xaxis.set_minor_locator(locmin)
#         ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
        #ax.set_xticks(np.logspace(-0.1, 8, 6, base=np.exp(1)))
        #ax.set_xticklabels(["%.2f" %d for d in np.exp(np.arange(-0.5, 2.1, 0.5))])
        ax.set_xlabel('Odds ratio (per 1-SD increase)')
        ax.set_title(f'{occ} {dis_label}\n n$_+$ = {int(or_multi_dic[pheno][dis+"_"+occ]["n"])} / {len(all_ecgs)}')
        ax.set_ylim([-1.0, len(ors)])
        ax.set_xlim([0.4, 3.0])
        plt.tight_layout()
        f.savefig(f'{dis}_{occ}_or_multi_overlap.png', dpi=500)

# %%
# scaled
import statsmodels.api as sm
hr_multi_dic = {}
covariates = ['bmi', 'age', 'male', 'cholesterol', 'HDL', 'current_smoker',
              'diastolic_bp', 'systolic_bp', 'c_lipidlowering', 'c_antihypertensive']
covariates_scale = ['bmi', 'age', 'cholesterol', 'HDL',
                    'diastolic_bp', 'systolic_bp']
for pheno in ['50_hrr_actual', 'pretest_model_50_hrr_predicted', 'resting_hr', '50_hrr_downsample_augment_prediction']:
    if pheno in ['FID', 'IID', 'instance0_date']: 
        continue
    hr_multi_dic[pheno] = {}
    tmp_pheno = all_ecgs[['sample_id', pheno, 'instance0_date'] + covariates]
    for disease, disease_label in disease_list:
        for occ in ['incident']:
            hr_multi_dic[pheno][f'{disease}_{occ}'] = {}
            tmp_data = tmp_pheno.merge(diseases_unpack[['sample_id', f'{disease}_{occ}', f'{disease}_censor_date']], left_on='sample_id', right_on='sample_id')
            std = np.std(tmp_data[pheno].values)
            tmp_data[pheno] = (tmp_data[pheno].values - np.mean(tmp_data[pheno].values))/std
            std = ", %.1f" % std
            tmp_data[covariates_scale] = (tmp_data[covariates_scale].values \
                                          - np.mean(tmp_data[covariates_scale].values, axis=0))/\
                                          np.std(tmp_data[covariates_scale].values, axis=0)
            tmp_data['futime'] = (tmp_data[f'{disease}_censor_date']-tmp_data['instance0_date']).dt.days
            tmp_data['entry'] = 0.0
            tmp_data['intercept'] = 1.0
            tmp_data = tmp_data[tmp_data['futime']>0]
            res = sm.PHReg(tmp_data['futime'], tmp_data[[pheno]+covariates], 
                           tmp_data[f'{disease}_{occ}'], tmp_data['entry']).fit()
            hr_multi_dic[pheno][f'{disease}_{occ}']['HR'] = np.exp(res.params[0])
            hr_multi_dic[pheno][f'{disease}_{occ}']['CI'] = np.exp(res.conf_int()[0])
            hr_multi_dic[pheno][f'{disease}_{occ}']['p'] = res.pvalues[0]
            hr_multi_dic[pheno][f'{disease}_{occ}']['n'] = np.sum(tmp_data[f'{disease}_{occ}'])
            hr_multi_dic[pheno][f'{disease}_{occ}']['std'] = std

# %%
%matplotlib inline
import matplotlib.pyplot as plt
import matplotlib
dis_plot_list = disease_list
phenos = or_multi_dic['50_hrr_actual'].keys()
for dis, dis_label in disease_list:
    for occ in ['incident']: 
        hrs = []
        cis_minus = []
        cis_plus = []
        labels = []
        for pheno in hr_multi_dic:
            if 'genetic' in pheno: 
                continue
            if 'hrr' in pheno:
                scale = 1.0
            elif 'age' in pheno:
                scale = 1.0
            else:
                scale = 1.0
            hrs.append(np.exp(np.log(hr_multi_dic[pheno][f'{dis}_{occ}']['HR'])*scale))
            cis_minus.append(np.exp(np.log(hr_multi_dic[pheno][f'{dis}_{occ}']['HR']-hr_multi_dic[pheno][f'{dis}_{occ}']['CI'][0])*scale))
            cis_plus.append(np.exp(np.log(hr_multi_dic[pheno][f'{dis}_{occ}']['CI'][1]-hr_multi_dic[pheno][f'{dis}_{occ}']['HR'])*scale))      
            labels.append(f'{label_dic[pheno][0]}{hr_multi_dic[pheno][dis+"_"+occ]["std"]} {label_dic[pheno][1]}')
            if hr_dic[pheno][f'{dis}_{occ}']['p'] < (0.05/len(hr_dic)):
                labels[-1] += '*'
        f, ax = plt.subplots()
        f.set_size_inches(3.3, 3)
        ax.errorbar(hrs, np.arange(len(hrs)), xerr=(cis_minus, cis_plus), marker='o', linestyle='', color='black')  
        ax.plot([1.0, 1.0], [-1.0, len(hrs)], 'k--')
        ax.set_yticks(np.arange(len(hrs)))
        ax.set_yticklabels(labels)
        ax.set_yticklabels([])
        ax.set_xscale('log', basex=np.exp(1))   
        ax.set_xticks([0.4, 0.8, 1.6])
        ax.set_xticklabels(map(str, [0.4, 0.8, 1.6]))
#         locmin = matplotlib.ticker.LogLocator(base=np.exp(1),subs=(0.3,0.35,0.4,0.45,
#                                                                0.6,0.7,0.8,0.9,
#                                                                1.2,1.4,1.6,1.8,
#                                                                2.4,2.8,3.2,3.6))
#         ax.xaxis.set_minor_locator(locmin)
#         ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
        #ax.set_xticks(np.logspace(-0.1, 8, 6, base=np.exp(1)))
        #ax.set_xticklabels(["%.2f" %d for d in np.exp(np.arange(-0.5, 2.1, 0.5))])
        ax.set_xlabel('Hazard ratio (per 1-SD increase)')
        ax.set_title(f'{occ} {dis_label}\n n$_+$ = {int(or_multi_dic[pheno][dis+"_"+occ]["n"])} / {len(all_ecgs)}')
        ax.set_ylim([-1.0, len(ors)])
        ax.set_xlim([0.4, 3.0])
        plt.tight_layout()
        f.savefig(f'{dis}_{occ}_hr_multi_overlap.png', dpi=500)

# %%
