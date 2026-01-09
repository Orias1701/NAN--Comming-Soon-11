import faiss
import fitz

from sentence_transformers import CrossEncoder

from Config import Configs
from Config import ModelLoader as ML
from Libraries import Common_MyUtils as MU, Common_TextProcess as TP, Common_PdfProcess as PP
from Libraries import PDF_QualityCheck as QualityCheck, PDF_ExtractData as ExtractData, PDF_MergeData as MergeData
from Libraries import Json_ChunkUnder as ChunkUnder, Json_GetStructures as GetStructures, Json_ChunkMaster as ChunkMaster, Json_SchemaExt as SchemaExt
from Libraries import Faiss_Embedding as F_Embedding, Faiss_Searching as F_Searching, Faiss_ChunkMapping as chunkMapper
from Libraries import Summarizer_Runner as SummaryRun


## ==============================
## CONFIGURATION
## ==============================

#### HARD CODE
service = "Categories"
infilename = "HNMU"
jsonKey = "paragraphs"
jsonField = "Text"

MODEL_DIR = "Models"
MODEL_SUMARY = "Summarizer"
MODEL_ENCODE = "Sentence_Transformer"


#### LOAD CONFIG
config = Configs.ConfigValues(pdfname=infilename, service=service)

pdfPath = config["pdfPath"]
exceptPath = config["exceptPath"]
markerPath = config["markerPath"]
statusPath = config["statusPath"]

rawDataPath = config["rawDataPath"]
rawLvlsPath = config["rawLvlsPath"]
structsPath = config["structsPath"]
segmentPath = config["segmentPath"]
schemaPath = config["schemaPath"]
faissPath = config["faissPath"]
mappingPath = config["mappingPath"]
mapDataPath = config["mapDataPath"]
mapChunkPath = config["mapChunkPath"]
metaPath = config["metaPath"]

serviceSegmentPath = config["serviceSegmentPath"]
serviceFaissPath = config["serviceFaissPath"]
serviceMappingPath = config["serviceMappingPath"]
serviceMapDataPath = config["serviceMapDataPath"]
serviceMapChunkPath = config["serviceMapChunkPath"]
serviceMetaPath = config["serviceMetaPath"]

DATA_KEY = config["DATA_KEY"]
EMBE_KEY = config["EMBE_KEY"]
SEARCH_EGINE = config["SEARCH_EGINE"]
RERANK_MODEL = config["RERANK_MODEL"]
RESPON_MODEL = config["RESPON_MODEL"]
EMBEDD_MODEL = config["EMBEDD_MODEL"]
CHUNKS_MODEL = config["CHUNKS_MODEL"]
SUMARY_MODEL = config["SUMARY_MODEL"]
WORD_LIMIT = config["WORD_LIMIT"]

EMBEDD_CACHED_MODEL = f"{MODEL_DIR}/{MODEL_ENCODE}/{EMBEDD_MODEL}"
CHUNKS_CACHED_MODEL = F"{MODEL_DIR}/{MODEL_ENCODE}/{CHUNKS_MODEL}"
SUMARY_CACHED_MODEL = f"{MODEL_DIR}/{MODEL_SUMARY}/{SUMARY_MODEL}"

MAX_INPUT = 1024
MAX_TARGET = 256
MIN_TARGET = 64
TRAIN_EPOCHS = 3
LEARNING_RATE = 3e-5
WEIGHT_DECAY = 0.01
BATCH_SIZE = 4




## ==============================
## EXCEPTIONS
## ==============================

#### FUNCTIONS
def loadHardcodes(filePath, wanted=None):
    data = MU.readJson(filePath)
    if "items" not in data:
        return
    result = {}
    for item in data["items"]:
        key = item["key"]
        if (not wanted) or (key in wanted):
            result[key] = item["values"]
    return result


#### LOAD EXCEPTIONS
exceptData = loadHardcodes(exceptPath, wanted=["common_words", "proper_names", "abbreviations"])
markerData = loadHardcodes(markerPath, wanted=["keywords", "markers"])
statusData = loadHardcodes(statusPath, wanted=["brackets", "sentence_ends"])




## ==============================
## MODELS
## ==============================

#### CLASS
Loader = ML.ModelLoader()


#### LOAD MODELS
indexer, embeddDevice = Loader.loadEncoder(EMBEDD_MODEL, EMBEDD_CACHED_MODEL)
chunker, chunksDevice = Loader.loadEncoder(CHUNKS_MODEL, CHUNKS_CACHED_MODEL)

tokenizer, summarizer, summaryDevice = Loader.loadSummarizer(SUMARY_MODEL, SUMARY_CACHED_MODEL)




## ==============================
## MAIN FLOW CLASSES
## ==============================

#### EXTRACTOR
checker = QualityCheck.PDFQualityChecker()

dataExtractor = ExtractData.B1Extractor(
    exceptData,
    markerData,
    statusData,
    properNameMinCount=10
)

merger = MergeData.ParagraphMerger()


#### STRUCT CHUNKER
structAnalyzer = GetStructures.StructureAnalyzer(
    verbose=True
)

chunkBuilder = ChunkMaster.ChunkBuilder()

schemaExt = SchemaExt.JSONSchemaExtractor(
    listPolicy="first", 
    verbose=True
)


#### INDEXER
faissIndexer = F_Embedding.DirectFaissIndexer(
    indexer=indexer,
    device=str(embeddDevice),
    batch_size=32,
    show_progress=True,
    flatten_mode="split",
    join_sep="\n",
    allowed_schema_types=("string", "array", "dict"),
    max_chars_per_text=2000,
    normalize=True,
    verbose=False
)


#### SEGMENT CHUNKER
chunkUnder = ChunkUnder.ChunkUndertheseaBuilder(
    embedder=indexer,
    device=embeddDevice,
    minWords=256,
    maxWords=768,
    simThreshold=0.7,
    keySentRatio=0.4
)


#### SUMMARIZER
summaryEngine = SummaryRun.RecursiveSummarizer(
    tokenizer=tokenizer,
    summarizer=summarizer,
    sumDevice=summaryDevice,
    chunkBuilder=chunkUnder,
    maxLength=200,
    minLength=100,
    maxDepth=4
)


#### SEARCHER
reranker = CrossEncoder(RERANK_MODEL, device=str(embeddDevice))
searchEngine = F_Searching.SemanticSearchEngine(
    indexer=indexer,
    reranker=reranker,
    device=str(embeddDevice),
    normalize=True,
    topK=20,
    rerankK=10,
    rerankBatchSize=16
)


## ==============================
## MAIN FLOW FUNCTIONS
## ==============================

### PREPROCESS

#### CHECKER
def pdfCheck(pdfDoc):
    isGood, metrics = checker.evaluate(pdfDoc)
    return isGood, metrics


#### EXTRACTOR
def extractRun(pdfDoc):
    extractedData = dataExtractor.extract(pdfDoc)
    rawDataDict = merger.merge(extractedData)
    return rawDataDict



### PROCESS FOR SEARCHING

#### STRUCT GETTER
def structRun(rawDataDict):
    markers =       structAnalyzer.extractMarkers(rawDataDict)
    structures =    structAnalyzer.buildStructures(markers)
    dedup =         structAnalyzer.deduplicate(structures)
    top =           structAnalyzer.selectTop(dedup)
    rawLvlsDict =   structAnalyzer.extendTop(top, dedup)
    
    print(MU.jsonConvert(rawLvlsDict, pretty=True))
    return rawLvlsDict


#### STRUCT CHUNKER
def chunkRun(RawLvlsDict=None, rawDataDict=None):
    StructsDict = chunkBuilder.build(RawLvlsDict, rawDataDict)
    return StructsDict


#### SEGMENT CHUNKER
def SegmentRun(StructsDict, RawLvlsDict):
    segmentDict = chunkBuilder.chunkClean(StructsDict, RawLvlsDict)
    return segmentDict


#### SCHEMA GETTER
def schemaRun(segmentDict):
    schemaDict = schemaExt.schemaRun(segmentDict=segmentDict)
    print(schemaDict)
    return schemaDict


#### INDEXER
def Indexing(schemaDict):
    faissIndex, mapping, mapData, chunkGroups = faissIndexer.buildFromJson(
        segmentPath=segmentPath,
        schemaDict=schemaDict,
        faissPath=faissPath,
        mapDataPath=mapDataPath,
        mappingPath=mappingPath,
        mapChunkPath=mapChunkPath
    )
    return faissIndex, mapping, mapData, chunkGroups



### PROCESS FOR CLASSIFICATION

#### RAW MERGER
def mergebyText(rawDataDict):
    mergedText = TP.mergeTxt(rawDataDict, jsonKey, jsonField)
    return mergedText


#### SUMMARIZER
def summaryRun(mergedText):
    summarized = summaryEngine.summarize(mergedText, minInput = 256, maxInput = 1024)
    return summarized



### FINAL PROCESS

#### SEARCHER
def runSearch(query, faissIndex, mapping, mapData, mapChunk):
    results = searchEngine.search(
        query=query,
        faissIndex=faissIndex,
        mapping=mapping,
        mapData=mapData,
        mapChunk=mapChunk,
        topK=20
    )
    return results


#### RERANKER
def runRerank(query, results):
    reranked = searchEngine.rerank(
        query=query,
        results=results,
        topK=10
    )
    return reranked


#### CHUNK MAPPER
def chunkMap(reranked, segmentDict, dropFields, fields, nChunks):
    mapResult = chunkMapper.processChunksPipeline(
        reranked=reranked, 
        segmentDict=segmentDict, 
        dropFields=dropFields,
        fields=fields,
        nChunks=nChunks
    )
    return mapResult




## ==============================
## MERGED FUNCTIONS
## ==============================

#### READ DATA
def ReadData(segmentPath, faissPath, mappingPath, mapDataPath, mapChunkPath):
    segmentDict = MU.readJson(segmentPath)
    faissIndex = faiss.read_index(faissPath)
    mapping = MU.readJson(mappingPath)
    mapData = MU.readJson(mapDataPath)
    mapChunk = MU.readJson(mapChunkPath)
    return {
        "segmentDict": segmentDict,
        "faissIndex": faissIndex,
        "mapping": mapping,
        "mapData": mapData,
        "mapChunk": mapChunk
    }
    

#### READ PDF
def preReadPDF(pdfPath=None, pdfBytes=None):
    if pdfBytes is not None:
        pdfDoc = fitz.open(stream=pdfBytes, filetype="pdf")
    elif pdfPath is not None:
        pdfDoc = fitz.open(pdfPath)
    else:
        return None
    
    checker = QualityCheck.PDFQualityChecker()
    is_good, info = checker.evaluate(pdfDoc)
    print(info)
    if is_good:
        print("[PASS] Tiếp tục xử lý.")
    else:
        print("[DENY] Bỏ qua file này.")
        pdfDoc.close()
        return None
        
    rawDataDict = extractRun(pdfDoc)
    MU.writeJson(rawDataDict, rawDataPath, indent=1)
    pdfDoc.close()
    
    return rawDataDict


#### PREPARE DATA
def PrepareData(segmentPath, faissPath, mappingPath, mapDataPath, mapChunkPath, rawDataDict=None):            
    if rawDataDict is not None:
        RawLvlsDict = structRun(rawDataDict)
        MU.writeJson(RawLvlsDict, rawLvlsPath, indent=2)

        StructsDict = chunkRun(RawLvlsDict, rawDataDict)
        MU.writeJson(StructsDict, structsPath, indent=2)

        segmentDict = SegmentRun(StructsDict, RawLvlsDict)
        MU.writeJson(segmentDict, segmentPath, indent=2)
        
    elif MU.fileExists(segmentPath):
        segmentDict = MU.readJson(segmentPath)
        
    else :
        return {
            "segmentDict": None,
            "faissIndex": None,
            "mapping": None,
            "mapData": None,
            "mapChunk": None
        }
    
    schemaDict = schemaRun(segmentDict)
    MU.writeJson(schemaDict, schemaPath, indent=2)

    faissIndex, mapping, mapData, chunkGroups = Indexing(schemaDict)
    MU.writeJson(mapping, mappingPath, indent=2)
    MU.writeJson(mapData, mapDataPath, indent=2)
    
    faiss.write_index(faissIndex, faissPath)
    MU.writeChunkmap(mapChunkPath, segmentPath, chunkGroups)
    mapChunk = MU.readJson(mapChunkPath)
    
    print("\nCompleted!")
    
    return {
        "segmentDict": segmentDict,
        "faissIndex": faissIndex,
        "mapping": mapping,
        "mapData": mapData,
        "mapChunk": mapChunk
    }
    
## ====================================================================================================