import logging
import os
import faiss

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["CUDA_LAUNCH_BLOCKING"] = "1"
os.environ["TORCH_USE_CUDA_DSA"] = "1"

def ConfigValues(pdfname="HNMU", service="Categories"):

    serviceFolder = f"./Services"
    assetsFolder = f"./Assets"
    dataFolder = f"./Database"

    servicePath = f"{serviceFolder}/{service}/{service}"
    serviceEmbeddingPath = f"{servicePath}_Embedding"
    serviceFaissPath = f"{serviceEmbeddingPath}_Index.faiss"
    serviceMappingPath = f"{serviceEmbeddingPath}_Mapping.json"
    serviceMapDataPath = f"{serviceEmbeddingPath}_MapData.json"
    serviceMapChunkPath = f"{serviceEmbeddingPath}_MapChunk.json"
    serviceMetaPath = f"{serviceEmbeddingPath}_Meta.json"
    serviceSegmentPath = f"{servicePath}_Segment.json"
    
    exceptPath = f"{assetsFolder}/ex.exceptions.json"
    markerPath = f"{assetsFolder}/ex.markers.json"
    statusPath = f"{assetsFolder}/ex.status.json"

    # Documents
    pdfFolder = f"./Documents"
    pdfPath = f"{pdfFolder}/{pdfname}.pdf"

    # Database
    dbPath = f"{dataFolder}/{pdfname}/{pdfname}"

    rawExtractPath = f"{dbPath}_Extract"
    chunksPath = f"{dbPath}_Chunks"
    embeddingPath = f"{dbPath}_Embedding"
    rawDataPath = f"{rawExtractPath}_Raw.json"
    rawLvlsPath = f"{rawExtractPath}_Levels.json"
    structsPath = f"{chunksPath}_Struct.json"
    segmentPath = f"{chunksPath}_Segment.json"
    schemaPath = f"{chunksPath}_Schema.json"
    faissPath = f"{embeddingPath}_Index.faiss"
    mappingPath = f"{embeddingPath}_Mapping.json"
    mapDataPath = f"{embeddingPath}_MapData.json"
    mapChunkPath = f"{embeddingPath}_MapChunk.json"
    metaPath = f"{embeddingPath}_Meta.json"

    # Keys
    DATA_KEY = "contents"
    EMBE_KEY = "embeddings"

    # Models
    SEARCH_EGINE = faiss.IndexFlatIP
    RERANK_MODEL = "BAAI/bge-reranker-base"
    CHUNKS_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
    EMBEDD_MODEL = "VoVanPhuc/sup-SimCSE-VietNamese-phobert-base"
    # EMBEDD_MODEL = "BAAI/bge-vi-base"
    RESPON_MODEL = "gpt-3.5-turbo"
    # PROMPT_FORMAT = """
    # <|im_start|>system
    # {system_prompt}<|im_end|>
    # <|im_start|>user
    # {prompt}<|im_end|>
    # <|im_start|>assistant
    # """

    SUMARY_MODEL = "LongK171/bartpho-syllable-vnexpress"

    WORD_LIMIT = 1000

    return {
        "pdfPath": pdfPath,
        "exceptPath": exceptPath,
        "markerPath": markerPath,
        "statusPath": statusPath,
        "rawDataPath": rawDataPath,
        "rawLvlsPath": rawLvlsPath,
        "structsPath": structsPath,
        "segmentPath": segmentPath,
        "schemaPath": schemaPath,
        "faissPath": faissPath,
        "mappingPath": mappingPath,
        "mapDataPath": mapDataPath,
        "mapChunkPath": mapChunkPath,
        "metaPath": metaPath,
        "serviceSegmentPath": serviceSegmentPath,
        "serviceFaissPath": serviceFaissPath,
        "serviceMappingPath": serviceMappingPath,
        "serviceMapDataPath": serviceMapDataPath,
        "serviceMapChunkPath": serviceMapChunkPath,
        "serviceMetaPath": serviceMetaPath,
        "DATA_KEY": DATA_KEY,
        "EMBE_KEY": EMBE_KEY,
        "SEARCH_EGINE": SEARCH_EGINE,
        "RERANK_MODEL": RERANK_MODEL,
        "RESPON_MODEL": RESPON_MODEL,        
        "CHUNKS_MODEL": CHUNKS_MODEL,
        "EMBEDD_MODEL": EMBEDD_MODEL,
        "SUMARY_MODEL": SUMARY_MODEL,
        "WORD_LIMIT": WORD_LIMIT
    }
