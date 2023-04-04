from optparse import OptionParser
from datetime import datetime
import pickle
import sys, os
sys.path.append(os.path.abspath('DomainPFP'))
import numpy as np
import pandas as pd
from tabulate import tabulate
pd.set_option('display.max_colwidth', None)

DOUBLE_PRECISION = 12       # precision for floating point

from domaingo_embedding_model import DomainGOEmbeddingModel, load_domaingo_embedding_model_weights
from domain_embedding import DomainEmbedding
from download_sequences import download_sequence
from utils import Ontology

parser = OptionParser(add_help_option=False)

parser.add_option('--protein',  help=  'Uniprot ID of protein')
parser.add_option('--fasta',  help='Fasta file of protein sequence')
parser.add_option('--threshMFO', type='float', default=.36, help='Threshold value for MFO prediction')
parser.add_option('--threshBPO', type='float', default=.31, help='Threshold value for BPO prediction')
parser.add_option('--threshCCO', type='float', default=.36, help='Threshold value for CCO prediction')

(options, args) = parser.parse_args()


def parse_domains(tsv_file_pth):
    """
    Parses the domains from the InterPro Scan results

    Args:
        tsv_file_pth (str): path to the tsv file
    """

    domains = []
    
    with open(tsv_file_pth,'r') as fp:
        dt = fp.read().split('\n')[:-1]
        for ln in dt:
            domains.append(ln.split('\t')[11])
    
    domains = set(domains)-set({'-'})

    return domains
    

def compute_embeddings(domains):
    """
    Computes the protein embedding from the domains 

    Args:
        domains (set or list): set or list of domains

    Returns:
        tuple of 3 numpy arrays: (MF embedding, BP embedding, CC embedding)
    """
                                                                                    
    domain_mapper_mf = pickle.load(open(os.path.join('data','processed','domain_mapper_netgo_mf.p'),'rb'))      # loading the mapper files
    go_mapper_mf = pickle.load(open(os.path.join('data','processed','go_mapper_netgo_mf.p'),'rb'))              
    mdl_mf = DomainGOEmbeddingModel(domain_mapper_mf,go_mapper_mf)                                              # creating a model
    mdl_mf = load_domaingo_embedding_model_weights(mdl_mf, os.path.join('saved_models','netgo_mf'))             # loading the model weights
    dmn_embedding_mf = DomainEmbedding(mdl_mf, domain_mapper_mf)                                                # creating the Domaing Embedding object

    domain_mapper_bp = pickle.load(open(os.path.join('data','processed','domain_mapper_netgo_bp.p'),'rb'))
    go_mapper_bp = pickle.load(open(os.path.join('data','processed','go_mapper_netgo_bp.p'),'rb'))
    mdl_bp = DomainGOEmbeddingModel(domain_mapper_bp,go_mapper_bp)
    mdl_bp = load_domaingo_embedding_model_weights(mdl_bp, os.path.join('saved_models','netgo_bp'))
    dmn_embedding_bp = DomainEmbedding(mdl_bp, domain_mapper_bp)

    domain_mapper_cc = pickle.load(open(os.path.join('data','processed','domain_mapper_netgo_cc.p'),'rb'))
    go_mapper_cc = pickle.load(open(os.path.join('data','processed','go_mapper_netgo_cc.p'),'rb'))
    mdl_cc = DomainGOEmbeddingModel(domain_mapper_cc,go_mapper_cc)
    mdl_cc = load_domaingo_embedding_model_weights(mdl_cc, os.path.join('saved_models','netgo_cc'))
    dmn_embedding_cc = DomainEmbedding(mdl_cc, domain_mapper_cc)


    mf_embedding = dmn_embedding_mf.get_embedding(-1)           # Initialize embeddings
    bp_embedding = dmn_embedding_bp.get_embedding(-1)
    cc_embedding = dmn_embedding_cc.get_embedding(-1)

    cnt = 0
    for dmn in domains:
        if dmn_embedding_mf.contains(dmn):
            mf_embedding += dmn_embedding_mf.get_embedding(dmn)
            cnt += 1
    if(cnt>1):
        mf_embedding /= cnt                     # averaging


    cnt = 0
    for dmn in domains:
        if dmn_embedding_bp.contains(dmn):
            bp_embedding += dmn_embedding_bp.get_embedding(dmn)
            cnt += 1
    if(cnt>1):
        bp_embedding /= cnt

    cnt = 0
    for dmn in domains:
        if dmn_embedding_cc.contains(dmn):
            cc_embedding += dmn_embedding_cc.get_embedding(dmn)
            cnt += 1
    if(cnt>1):
        cc_embedding /= cnt


    mf_embedding = np.round(mf_embedding,DOUBLE_PRECISION)
    bp_embedding = np.round(bp_embedding,DOUBLE_PRECISION)
    cc_embedding = np.round(cc_embedding,DOUBLE_PRECISION)

    return mf_embedding, bp_embedding, cc_embedding


def predict_functions(mf_embedding, bp_embedding, cc_embedding):
    """
    Predict functions of the protein using KNN

    Args:
        mf_embedding (_type_): _description_
        bp_embedding (_type_): _description_
        cc_embedding (_type_): _description_

    Returns:
        _type_: _description_
    """

    knn_mdl_mf = pickle.load(open(os.path.join('saved_models','knn_netgo_mf.p'),'rb'))
    knn_mdl_bp = pickle.load(open(os.path.join('saved_models','knn_netgo_bp.p'),'rb'))
    knn_mdl_cc = pickle.load(open(os.path.join('saved_models','knn_netgo_cc.p'),'rb'))

    all_protein_domains_mf = pickle.load(open(os.path.join('data','processed','all_protein_domains_netgo_mf_train.p'),'rb'))
    all_protein_domains_bp = pickle.load(open(os.path.join('data','processed','all_protein_domains_netgo_bp_train.p'),'rb'))
    all_protein_domains_cc = pickle.load(open(os.path.join('data','processed','all_protein_domains_netgo_cc_train.p'),'rb'))
    all_protein_gos_mf = pickle.load(open(os.path.join('data','processed','all_protein_go_netgo_mf_train.p'),'rb'))
    all_protein_gos_bp = pickle.load(open(os.path.join('data','processed','all_protein_go_netgo_bp_train.p'),'rb'))
    all_protein_gos_cc = pickle.load(open(os.path.join('data','processed','all_protein_go_netgo_cc_train.p'),'rb'))
    
    prtns_mf = set(all_protein_domains_mf.keys())
    prtns_mf = prtns_mf.intersection(set(all_protein_gos_mf.keys()))
    prtns_mf = list(prtns_mf)
    prtns_mf.sort()
    prtns_bp = set(all_protein_domains_bp.keys())
    prtns_bp = prtns_bp.intersection(set(all_protein_gos_bp.keys()))
    prtns_bp = list(prtns_bp)
    prtns_bp.sort()
    prtns_cc = set(all_protein_domains_cc.keys())
    prtns_cc = prtns_cc.intersection(set(all_protein_gos_cc.keys()))
    prtns_cc = list(prtns_cc)
    prtns_cc.sort()

    go_terms_mf = []
    for prtn in prtns_mf:
        if(len(all_protein_domains_mf[prtn])==0):
            continue
        go_terms_mf.append(all_protein_gos_mf[prtn])
    go_terms_bp = []
    for prtn in prtns_bp:
        if(len(all_protein_domains_bp[prtn])==0):
            continue
        go_terms_bp.append(all_protein_gos_bp[prtn])
    go_terms_cc = []
    for prtn in prtns_cc:
        if(len(all_protein_domains_cc[prtn])==0):
            continue
        go_terms_cc.append(all_protein_gos_cc[prtn])

    go_preds_mf = knn_mdl_mf.get_neighbor_go_terms_proba_batch(go_terms_mf, [mf_embedding])[0]
    go_preds_bp = knn_mdl_bp.get_neighbor_go_terms_proba_batch(go_terms_bp, [bp_embedding])[0]
    go_preds_cc = knn_mdl_cc.get_neighbor_go_terms_proba_batch(go_terms_cc, [cc_embedding])[0]

    return (go_preds_mf,go_preds_bp,go_preds_cc)

def main():
    """
    Predicts the functions of a query protein
    """

    protein = ''
    fasta = ''
    thresh_mf = .36
    thresh_bp = .31
    thresh_cc = .36

    onto_tree = Ontology(f'data/go.obo', with_rels=False) 
    
    if options.protein:
        protein = options.protein

    if options.fasta:
        fasta = options.fasta

    if options.threshMFO:
        thresh_mf = options.threshMFO

    if options.threshBPO:
        thresh_bp = options.threshBPO

    if options.threshCCO:
        thresh_cc = options.threshCCO

    if len(protein)>0:
        print(f'Downloading sequence of {protein} from UniProt')
        flg = download_sequence(protein)
        if(not flg):
            sys.exit()
        else:
            fasta = os.path.join('temp_data',protein+'.fasta')


    elif len(fasta)>0:
        print(f'Loading the fasta file {fasta}')
        if(not os.path.isfile(fasta)):
            print(f'{fasta} file not found')
            sys.exit()

    else:
        print('Please input a protein UniProt ID or path to a fasta file')
        sys.exit()

    try:
        os.makedirs('temp_data')
    except:
        pass
    
    
    job_id = datetime.now().strftime("%H%M%S%f")

    print('Extracting protein domains using InterPro Scan')
    os.system(f'python3 DomainPFP/iprscan5.py --email domainpfp@gmail.com --sequence {fasta} --outfile temp_data/{job_id}')
    print("Domains Computed")
    domains = parse_domains(os.path.join('temp_data',f'{job_id}.tsv.tsv'))

    print("Computing Embeddings")
    mf_embedding, bp_embedding, cc_embedding = compute_embeddings(domains)

    print("Predicting Functions")
    go_preds_mf, go_preds_bp, go_preds_cc = predict_functions(mf_embedding, bp_embedding, cc_embedding)

    print('===================')
    print('Molecular Functions')
    print('===================')
    mf_df = []
    for go_trm in go_preds_mf:
        if go_preds_mf[go_trm]>thresh_mf:
            mf_df.append([go_trm, (round(go_preds_mf[go_trm],3)),onto_tree.ont[go_trm]['name']])
    mf_df = pd.DataFrame(mf_df,columns=['GO Term','Confidence','Definition'])
    mf_df = mf_df.sort_values('Confidence',ascending=False).reset_index(drop=True)

    
    print(tabulate(mf_df, headers='keys', tablefmt='grid'))



    print('==================')
    print('Biological Process')
    print('==================')
    bp_df = []
    for go_trm in go_preds_bp:
        if go_preds_bp[go_trm]>thresh_bp:            
            bp_df.append([go_trm, (round(go_preds_bp[go_trm],3)),onto_tree.ont[go_trm]['name']])
    bp_df = pd.DataFrame(bp_df,columns=['GO Term','Confidence','Definition'])
    bp_df = bp_df.sort_values('Confidence',ascending=False).reset_index(drop=True)
    
    print(tabulate(bp_df, headers='keys', tablefmt='grid'))

    print('===================')
    print('Cellular Components')
    print('===================')
    cc_df = []
    for go_trm in go_preds_cc:
        if go_preds_cc[go_trm]>thresh_cc:
            cc_df.append([go_trm, (round(go_preds_cc[go_trm],3)),onto_tree.ont[go_trm]['name']])
    cc_df = pd.DataFrame(cc_df,columns=['GO Term','Confidence','Definition'])
    cc_df = cc_df.sort_values('Confidence',ascending=False).reset_index(drop=True)
    
    print(tabulate(cc_df, headers='keys', tablefmt='grid'))



if __name__=='__main__':
    main()