import os
import numpy as np
import pandas as pd
import json

from typing import Optional, Union

import evaluate
from datasets import Dataset, DatasetDict, load_from_disk

from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
    DataCollatorForSeq2Seq,
    Seq2SeqTrainer,
    Seq2SeqTrainingArguments,
    EarlyStoppingCallback,
    set_seed,
)


class SummarizationTrainer:
    """
    Fine-tune mô hình tóm tắt (Seq2Seq) đa dụng — thống nhất interface:
    run(Checkpoint, ModelPath, DataPath | dataset, tokenizer)
    """

    def __init__(
        self,
        maxInputLength: int = 1024,
        maxTargetLength: int = 256,
        prefix: str = "",
        inputColumn: str = "article",
        targetColumn: str = "summary",
        learningRate: float = 3e-5,
        weightDecay: float = 0.01,
        batchSize: int = 8,
        numTrainEpochs: int = 3,
        gradientAccumulationSteps: int = 1,
        warmupRatio: float = 0.05,
        lrSchedulerType: str = "linear",
        seed: int = 42,
        numBeams: int = 4,
        generationMaxLength: Optional[int] = None,
        fp16: bool = True,
        earlyStoppingPatience: int = 2,
        loggingSteps: int = 200,
        reportTo: str = "none",
    ):
        # Hyperparams
        self.maxInputLength = maxInputLength
        self.maxTargetLength = maxTargetLength
        self.prefix = prefix
        self.inputColumn = inputColumn
        self.targetColumn = targetColumn

        self.learningRate = learningRate
        self.weightDecay = weightDecay
        self.batchSize = batchSize
        self.numTrainEpochs = numTrainEpochs
        self.gradientAccumulationSteps = gradientAccumulationSteps
        self.warmupRatio = warmupRatio
        self.lrSchedulerType = lrSchedulerType
        self.seed = seed

        self.numBeams = numBeams
        self.generationMaxLength = generationMaxLength
        self.fp16 = fp16
        self.earlyStoppingPatience = earlyStoppingPatience
        self.loggingSteps = loggingSteps
        self.reportTo = reportTo

        self._rouge = evaluate.load("rouge")
        self._tokenizer = None
        self._model = None

    # =========================================================
    # 1️⃣  Đọc dữ liệu JSONL hoặc Arrow
    # =========================================================
    def _loadJsonlToDatasetdict(self, dataPath: str) -> DatasetDict:
        print(f"Đang tải dữ liệu từ {dataPath} ...")
        dataList = []
        with open(dataPath, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    dataList.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        df = pd.DataFrame(dataList)
        if self.inputColumn not in df or self.targetColumn not in df:
            raise ValueError(f"File {dataPath} thiếu cột {self.inputColumn}/{self.targetColumn}")
        df = df[[self.inputColumn, self.targetColumn]].dropna()

        dataset = Dataset.from_pandas(df, preserve_index=False)
        split = dataset.train_test_split(test_size=0.1, seed=self.seed)
        print(f"✔ Dữ liệu chia: {len(split['train'])} train / {len(split['test'])} validation")
        return DatasetDict({"train": split["train"], "validation": split["test"]})

    def _ensureDatasetdict(self, dataset: Optional[Union[Dataset, DatasetDict]], dataPath: Optional[str]) -> DatasetDict:
        if dataset is not None:
            if isinstance(dataset, DatasetDict):
                return dataset
            if isinstance(dataset, Dataset):
                split = dataset.train_test_split(test_size=0.1, seed=self.seed)
                return DatasetDict({"train": split["train"], "validation": split["test"]})
            raise TypeError("dataset phải là datasets.Dataset hoặc datasets.DatasetDict.")
        if dataPath:
            if os.path.isdir(dataPath):
                print(f"Load DatasetDict từ thư mục Arrow: {dataPath}")
                return load_from_disk(dataPath)
            return self._loadJsonlToDatasetdict(dataPath)
        raise ValueError("Cần truyền dataset hoặc dataPath")

    # =========================================================
    # 2️⃣  Token hóa
    # =========================================================
    def _preprocessFunction(self, examples):
        inputs = examples[self.inputColumn]
        if self.prefix:
            inputs = [self.prefix + x for x in inputs]
        modelInputs = self._tokenizer(inputs, maxLength=self.maxInputLength, truncation=True)
        with self._tokenizer.as_target_tokenizer():
            labels = self._tokenizer(examples[self.targetColumn], maxLength=self.maxTargetLength, truncation=True)
        modelInputs["labels"] = labels["input_ids"]
        return modelInputs

    # =========================================================
    # 3️⃣  Tính điểm ROUGE
    # =========================================================
    def _computeMetrics(self, evalPred):
        preds, labels = evalPred
        decodedPreds = self._tokenizer.batch_decode(preds, skip_special_tokens=True)
        labels = np.where(labels != -100, labels, self._tokenizer.pad_token_id)
        decodedLabels = self._tokenizer.batch_decode(labels, skip_special_tokens=True)
        result = self._rouge.compute(predictions=decodedPreds, references=decodedLabels, use_stemmer=True)
        return {k: round(v * 100, 4) for k, v in result.items()}

    # =========================================================
    # 4️⃣  Chạy huấn luyện
    # =========================================================
    def run(
        self,
        checkpoint: str,
        modelPath: str,
        dataPath: Optional[str] = None,
        dataset: Optional[Union[Dataset, DatasetDict]] = None,
        tokenizer: Optional[AutoTokenizer] = None,
    ):
        set_seed(self.seed)
        ds = self._ensureDatasetdict(dataset, dataPath)
        self._tokenizer = tokenizer or AutoTokenizer.from_pretrained(checkpoint)
        print(f"Tải model checkpoint: {checkpoint}")
        self._model = AutoModelForSeq2SeqLM.from_pretrained(checkpoint)

        print("Tokenizing dữ liệu ...")
        tokenized = ds.map(self._preprocessFunction, batched=True)
        dataCollator = DataCollatorForSeq2Seq(tokenizer=self._tokenizer, model=self._model)
        genMaxLen = self.generationMaxLength or self.maxTargetLength

        trainingArgs = Seq2SeqTrainingArguments(
            output_dir=modelPath,
            evaluation_strategy="epoch",
            save_strategy="epoch",
            learning_rate=self.learningRate,
            per_device_train_batch_size=self.batchSize,
            per_device_eval_batch_size=self.batchSize,
            weight_decay=self.weightDecay,
            num_train_epochs=self.numTrainEpochs,
            predict_with_generate=True,
            generation_max_length=genMaxLen,
            generation_num_beams=self.numBeams,
            fp16=self.fp16,
            gradient_accumulation_steps=self.gradientAccumulationSteps,
            warmup_ratio=self.warmupRatio,
            lr_scheduler_type=self.lrSchedulerType,
            logging_steps=self.loggingSteps,
            load_best_model_at_end=True,
            metric_for_best_model="rougeL",
            greater_is_better=True,
            save_total_limit=3,
            report_to=self.reportTo,
        )

        trainer = Seq2SeqTrainer(
            model=self._model,
            args=trainingArgs,
            train_dataset=tokenized["train"],
            eval_dataset=tokenized["validation"],
            tokenizer=self._tokenizer,
            data_collator=dataCollator,
            compute_metrics=self._computeMetrics,
            callbacks=[EarlyStoppingCallback(early_stopping_patience=self.earlyStoppingPatience)],
        )

        print("\n🚀 BẮT ĐẦU HUẤN LUYỆN ...")
        trainer.train()
        print("✅ HUẤN LUYỆN HOÀN TẤT.")
        trainer.save_model(modelPath)
        self._tokenizer.save_pretrained(modelPath)
        print(f"💾 Đã lưu model & tokenizer tại: {modelPath}")
        return trainer

    # =========================================================
    # 5️⃣  Sinh tóm tắt
    # =========================================================
    def generate(self, text: str, maxNewTokens: Optional[int] = None) -> str:
        if self._model is None or self._tokenizer is None:
            raise RuntimeError("Model/tokenizer chưa khởi tạo, hãy gọi run() trước.")
        prompt = (self.prefix + text) if self.prefix else text
        inputs = self._tokenizer(prompt, return_tensors="pt", truncation=True, maxLength=self.maxInputLength)
        genLen = maxNewTokens or self.maxTargetLength
        outputs = self._model.generate(**inputs, maxNewTokens=genLen, numBeams=self.numBeams)
        return self._tokenizer.decode(outputs[0], skip_special_tokens=True)

    # =========================================================
    # 6️⃣  Load lại Dataset Arrow
    # =========================================================
    @staticmethod
    def loadLocalDataset(dataPath: str) -> DatasetDict:
        return load_from_disk(dataPath)
